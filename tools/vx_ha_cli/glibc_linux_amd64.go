package main

import "embed"

//go:embed glibc/amd64
var glibcFS embed.FS

const (
	glibcDir    = "glibc/amd64"
	glibcLoader = "ld-linux-x86-64.so.2"
)
