// vx_ha_cli — thin CLI wrapper around vx_puppet, built for the Home Assistant
// veracross integration. Always emits machine-readable JSON:
//
//	success: {"ok": true, "grades": [...]}
//	failure: {"ok": false, "error": "..."}
//
// on stdout as the *last* line (lightpanda's own output may precede it on
// stdout, so the Python side parses the last non-empty line as JSON).
// Progress logging goes to stderr.
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

func logf(format string, args ...any) { log.Printf(format, args...) }

func main() {
	log.SetOutput(os.Stderr)
	log.SetFlags(log.Ltime)

	// run() returns instead of os.Exit-ing so its defers (killing lightpanda)
	// always execute; previously every login failure orphaned a browser.
	grades, err := run()
	if err != nil {
		emit(result{OK: false, Error: err.Error()})
		os.Exit(1)
	}
	emit(result{OK: true, Grades: grades})
}

func run() ([]vx_puppet.GradeInfo, error) {
	var (
		schoolID = flag.String("school", "", "School ID")
		username = flag.String("user", "", "Username / student ID")
		password = flag.String("pass", "", "Password")
		port     = flag.Int("port", 0, "Chromedp-compatible DevTools browser port (0 = random)")
		timeout  = flag.Duration("timeout", 90*time.Second, "Request timeout")
		remote   = flag.Bool("external", false, "Use external browser already running on -port")
		lpDir    = flag.String("lightpanda-dir", "lightpanda", "Dir to download/cache the lightpanda binary in")
	)
	flag.Parse()

	if *username == "" || *password == "" || *schoolID == "" {
		return nil, fmt.Errorf("schoolID, username, and password are required (-school, -user, -pass)")
	}

	if *port == 0 {
		*port = 20000 + rand.Intn(20000)
	}

	ctx, cancel := context.WithTimeout(context.Background(), *timeout+30*time.Second)
	defer cancel()

	if !*remote {
		lp, err := ensureLightpanda(ctx, *lpDir)
		if err != nil {
			return nil, fmt.Errorf("download lightpanda: %w", err)
		}
		exe, err := wrapLightpanda(lp)
		if err != nil {
			return nil, fmt.Errorf("prepare lightpanda runtime: %w", err)
		}
		logf("starting lightpanda on port %d", *port)
		browser, err := vx_puppet.StartLightpanda(ctx, exe, *port)
		if err != nil {
			return nil, fmt.Errorf("start lightpanda: %w", err)
		}
		defer browser.Close()
	}

	client, err := vx_puppet.New(vx_puppet.Options{
		WebSocketURL: fmt.Sprintf("ws://127.0.0.1:%d/devtools/browser", *port),
		SchoolID:     *schoolID,
		Timeout:      *timeout,
	})
	if err != nil {
		return nil, fmt.Errorf("client init: %w", err)
	}
	defer client.Close()

	logf("logging in")
	if err := client.Login(*username, *password); err != nil {
		return nil, fmt.Errorf("login: %w", err)
	}

	logf("fetching grades")
	grades, err := client.GetGrades()
	if err != nil {
		return nil, fmt.Errorf("get grades: %w", err)
	}
	return grades, nil
}
