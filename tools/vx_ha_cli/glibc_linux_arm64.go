package main

import "embed"

//go:embed glibc/arm64
var glibcFS embed.FS

const (
	glibcDir    = "glibc/arm64"
	glibcLoader = "ld-linux-aarch64.so.1"
)
