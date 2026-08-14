// vx_ha_cli — thin CLI wrapper around vx_puppet, built for the Home Assistant
// veracross integration. Always emits machine-readable JSON:
//
//	success: {"ok": true, "grades": [...]}
//	failure: {"ok": false, "error": "..."}
//
// on stdout as the *last* line (progress/log noise may precede it on stdout
// too, so the Python side should parse the last non-empty line as JSON).
package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"math/rand"
	"os"
	"time"

	"github.com/mcMineyC/vx_puppet"
)

type result struct {
	OK     bool                  `json:"ok"`
	Error  string                `json:"error,omitempty"`
	Grades []vx_puppet.GradeInfo `json:"grades,omitempty"`
}

func emit(r result) {
	b, _ := json.Marshal(r)
	fmt.Println(string(b))
}

func fail(err error) {
	emit(result{OK: false, Error: err.Error()})
	os.Exit(1)
}

func main() {
	ctx := context.Background()

	var (
		schoolID = flag.String("school", "", "School ID")
		username = flag.String("user", "", "Username / student ID")
		password = flag.String("pass", "", "Password")
		port     = flag.Int("port", 0, "Chromedp-compatible DevTools browser port (0 = random)")
		timeout  = flag.Duration("timeout", 90*time.Second, "Request timeout")
		remote   = flag.Bool("external", false, "Use external browser already running on -port")
		lpDir    = flag.String("lightpanda-dir", "", "Dir to download/cache the lightpanda binary in")
	)
	flag.Parse()

	log.SetOutput(os.Stderr)

	if *username == "" || *password == "" || *schoolID == "" {
		fail(fmt.Errorf("schoolID, username, and password are required (-school, -user, -pass)"))
	}

	if *port == 0 {
		rand.Seed(time.Now().UnixNano())
		*port = 20000 + rand.Intn(20000)
	}

	if *lpDir == "" {
		*lpDir = "lightpanda"
	}

	var browser *vx_puppet.LightpandaInstance

	if !(*remote) {
		binaryPath, err := vx_puppet.DownloadLightpanda(ctx, *lpDir)
		if err != nil {
			fail(fmt.Errorf("download lightpanda: %w", err))
		}

		browser, err = vx_puppet.StartLightpanda(ctx, binaryPath, *port)
		if err != nil {
			fail(fmt.Errorf("start lightpanda: %w", err))
		}
		defer browser.Close()
	}

	client, err := vx_puppet.New(vx_puppet.Options{
		WebSocketURL: fmt.Sprintf("ws://127.0.0.1:%d/devtools/browser", *port),
		SchoolID:     *schoolID,
		Timeout:      *timeout,
	})
	if err != nil {
		fail(fmt.Errorf("client init: %w", err))
	}
	defer client.Close()

	if err := client.Login(*username, *password); err != nil {
		fail(fmt.Errorf("login: %w", err))
	}

	grades, err := client.GetGrades()
	if err != nil {
		fail(fmt.Errorf("get grades: %w", err))
	}

	emit(result{OK: true, Grades: grades})
}
