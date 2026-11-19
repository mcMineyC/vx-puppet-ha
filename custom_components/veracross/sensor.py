"""Sensors — one per class, created dynamically as grade data arrives."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_SCHOOL, DATA_MANAGER, DOMAIN, SIGNAL_GRADES_UPDATED
from .manager import VeracrossManager, parse_percent, slugify_class as _slug


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    manager: VeracrossManager = hass.data[DOMAIN][entry.entry_id][DATA_MANAGER]
    known_classes: set[str] = set()

    def _device_info() -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"Veracross ({entry.data[CONF_SCHOOL]})",
            manufacturer="Veracross (unofficial)",
        )

    @callback
    def _handle_grades(grades: list[dict]) -> None:
        new_entities = []
        for grade in grades:
            class_name = grade.get("class", "")
            slug = _slug(class_name)
            if not slug or slug in known_classes:
                continue
            known_classes.add(slug)
            new_entities.append(
                VeracrossGradeSensor(entry, manager, slug, class_name, _device_info())
            )
        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            SIGNAL_GRADES_UPDATED.format(entry_id=entry.entry_id),
            _handle_grades,
        )
    )

    # in case grades already landed before this platform finished setting up
    if manager.grades:
        _handle_grades(manager.grades)


class VeracrossGradeSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_icon = "mdi:school"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        entry: ConfigEntry,
        manager: VeracrossManager,
        slug: str,
        class_name: str,
        device_info: DeviceInfo,
    ) -> None:
        self._entry = entry
        self._manager = manager
        self._slug = slug
        self._attr_name = class_name
        self._attr_unique_id = f"{entry.entry_id}_class_{slug}"
        self._attr_device_info = device_info

    def _find(self) -> dict | None:
        for grade in self._manager.grades:
            if _slug(grade.get("class", "")) == self._slug:
                return grade
        return None

    @property
    def native_value(self) -> float | None:
        grade = self._find()
        return parse_percent(grade.get("grade")) if grade else None

    @property
    def extra_state_attributes(self) -> dict:
        grade = self._find()
        if not grade:
            return {}
        return {
            "class": grade.get("class"),
            "grade_letter": grade.get("gradeLetter"),
            "grade_raw": grade.get("grade"),
            "new_updates": grade.get("new_updates"),
        }

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_GRADES_UPDATED.format(entry_id=self._entry.entry_id),
                self._handle_update,
            )
        )

    @callback
    def _handle_update(self, _grades: list[dict]) -> None:
        self.async_write_ha_state()
