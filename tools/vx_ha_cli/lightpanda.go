package main

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"io/fs"
	"net/http"
	"os"
	"path"
	"path/filepath"
	"runtime"
	"strings"
)

// lightpanda's Linux builds are dynamically linked against glibc (>= 2.35).
// Home Assistant's container image is Alpine (musl), which has no
// /lib64/ld-linux-*.so, so exec'ing lightpanda there fails with a confusing
// "no such file or directory". We ship a minimal glibc runtime (loader +
// libc + libm from Debian's libc6 package) embedded in this binary, unpack
// it next to lightpanda, and launch lightpanda through that loader via a
// tiny /bin/sh wrapper (vx_puppet.StartLightpanda only takes a binary path).

const minLightpandaSize = 10 << 20 // real builds are ~75MB; anything tiny is a truncated download

func lightpandaURL() (string, error) {
	arch := map[string]string{"amd64": "x86_64", "arm64": "aarch64"}[runtime.GOARCH]
	osName := map[string]string{"linux": "linux", "darwin": "macos"}[runtime.GOOS]
	if arch == "" || osName == "" {
		return "", fmt.Errorf("unsupported platform: %s/%s", runtime.GOOS, runtime.GOARCH)
	}
	return fmt.Sprintf("https://github.com/lightpanda-io/browser/releases/download/nightly/lightpanda-%s-%s", arch, osName), nil
}

// ensureLightpanda returns the path to a usable lightpanda binary in dir,
// downloading it if missing or if a previous download was truncated.
// Downloads go to a temp file and are renamed into place only on success.
func ensureLightpanda(ctx context.Context, dir string) (string, error) {
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return "", err
	}
	dest := filepath.Join(dir, "lightpanda")
	if st, err := os.Stat(dest); err == nil && st.Size() >= minLightpandaSize {
		if err := os.Chmod(dest, 0o755); err != nil {
			return "", err
		}
		return dest, nil
	}

	url, err := lightpandaURL()
	if err != nil {
		return "", err
	}
	logf("downloading lightpanda from %s", url)
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return "", err
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("download lightpanda: HTTP %s", resp.Status)
	}

	tmp, err := os.CreateTemp(dir, "lightpanda-*.part")
	if err != nil {
		return "", err
	}
	defer os.Remove(tmp.Name()) // no-op after successful rename
	n, err := io.Copy(tmp, resp.Body)
	if cerr := tmp.Close(); err == nil {
		err = cerr
	}
	if err != nil {
		return "", fmt.Errorf("download lightpanda: %w", err)
	}
	if n < minLightpandaSize {
		return "", fmt.Errorf("download lightpanda: only got %d bytes", n)
	}
	if err := os.Chmod(tmp.Name(), 0o755); err != nil {
		return "", err
	}
	if err := os.Rename(tmp.Name(), dest); err != nil {
		return "", err
	}
	return dest, nil
}

// wrapLightpanda returns the path to exec in place of lightpanda. On
// linux/{amd64,arm64} that's a shell wrapper that runs lightpanda via the
// bundled glibc loader; elsewhere it's lightpanda itself.
func wrapLightpanda(lpPath string) (string, error) {
	if glibcDir == "" {
		return lpPath, nil
	}
	dir := filepath.Join(filepath.Dir(lpPath), "glibc")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return "", err
	}

	entries, err := fs.ReadDir(glibcFS, glibcDir)
	if err != nil {
		return "", err
	}
	for _, e := range entries {
		data, err := glibcFS.ReadFile(path.Join(glibcDir, e.Name()))
		if err != nil {
			return "", err
		}
		if err := writeIfChanged(filepath.Join(dir, e.Name()), data, 0o755); err != nil {
			return "", err
		}
	}

	script := fmt.Sprintf("#!/bin/sh\nexec %s --library-path %s %s \"$@\"\n",
		shQuote(filepath.Join(dir, glibcLoader)), shQuote(dir), shQuote(lpPath))
	wrapper := filepath.Join(filepath.Dir(lpPath), "lightpanda-run.sh")
	if err := writeIfChanged(wrapper, []byte(script), 0o755); err != nil {
		return "", err
	}
	return wrapper, nil
}

func writeIfChanged(p string, data []byte, mode os.FileMode) error {
	if cur, err := os.ReadFile(p); err == nil && bytes.Equal(cur, data) {
		return os.Chmod(p, mode)
	}
	tmp := p + ".tmp"
	if err := os.WriteFile(tmp, data, mode); err != nil {
		return err
	}
	if err := os.Chmod(tmp, mode); err != nil {
		return err
	}
	return os.Rename(tmp, p)
}

func shQuote(s string) string {
	return "'" + strings.ReplaceAll(s, "'", `'\''`) + "'"
}
