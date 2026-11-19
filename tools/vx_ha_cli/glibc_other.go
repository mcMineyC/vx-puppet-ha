//go:build !(linux && (amd64 || arm64))

package main

import "embed"

// No bundled glibc off linux/{amd64,arm64}; lightpanda is exec'd directly.
var glibcFS embed.FS

const (
	glibcDir    = ""
	glibcLoader = ""
)
