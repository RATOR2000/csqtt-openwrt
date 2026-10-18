//go:build linux

// Test-only private mount view. fw4 print and nft -c never load a ruleset.
package main

import (
	"bytes"
	"context"
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"syscall"
	"time"
)

func main() {
	result := map[string]bool{"private_mount": false, "full_files_absent": false, "hold_present": false,
		"fw4_print": false, "fw4_has_hold": false, "fw4_missing_full_includes": false, "native_check": false}
	exitCode := 1
	defer func() { json.NewEncoder(os.Stdout).Encode(result); os.Exit(exitCode) }()
	if len(os.Args) != 2 || os.Geteuid() != 0 {
		return
	}
	dir := filepath.Clean(os.Args[1])
	if dir != "/tmp/boot7-mount-proof" {
		return
	}
	info, err := os.Lstat(dir)
	if err != nil || !info.IsDir() || info.Mode().Perm() != 0700 {
		return
	}
	view := filepath.Join(dir, "view")
	info, err = os.Lstat(view)
	if err != nil || !info.IsDir() || info.Mode().Perm() != 0700 {
		return
	}
	data, err := os.ReadFile("/etc/csqtt/hold.nft")
	if err != nil {
		return
	}
	if err = os.WriteFile(filepath.Join(view, "hold.nft"), data, 0600); err != nil {
		return
	}
	runtime.LockOSThread()
	before, err := os.Readlink("/proc/self/ns/mnt")
	if err != nil {
		return
	}
	if syscall.Unshare(syscall.CLONE_NEWNS) != nil {
		return
	}
	if syscall.Mount("", "/", "", syscall.MS_REC|syscall.MS_PRIVATE, "") != nil {
		return
	}
	if syscall.Mount(view, "/etc/csqtt", "", syscall.MS_BIND, "") != nil {
		return
	}
	defer syscall.Unmount("/etc/csqtt", syscall.MNT_DETACH)
	if syscall.Mount("", "/etc/csqtt", "", syscall.MS_BIND|syscall.MS_REMOUNT|syscall.MS_RDONLY, "") != nil {
		return
	}
	after, err := os.Readlink("/proc/self/ns/mnt")
	if err != nil || after == before {
		return
	}
	result["private_mount"] = true
	result["full_files_absent"] = true
	for _, name := range []string{"policy.json", "policy.nft", "forward.nft", "input.nft"} {
		_, err = os.Stat(filepath.Join("/etc/csqtt", name))
		if !os.IsNotExist(err) {
			result["full_files_absent"] = false
			return
		}
	}
	present, err := os.ReadFile("/etc/csqtt/hold.nft")
	if err != nil || !bytes.Equal(present, data) {
		return
	}
	result["hold_present"] = true
	ctx, cancel := context.WithTimeout(context.Background(), 12*time.Second)
	defer cancel()
	cmd := exec.CommandContext(ctx, "/sbin/fw4", "print")
	var diagnostics bytes.Buffer
	cmd.Stderr = &diagnostics
	rules, err := cmd.Output()
	os.WriteFile(filepath.Join(dir, "fw4-print.stderr.private.log"), diagnostics.Bytes(), 0600)
	if err != nil {
		return
	}
	result["fw4_print"] = true
	result["fw4_has_hold"] = bytes.Contains(rules, []byte("include \"/etc/csqtt/hold.nft\""))
	result["fw4_missing_full_includes"] = true
	for _, name := range []string{"policy.nft", "forward.nft", "input.nft"} {
		if bytes.Contains(rules, []byte("include \"/etc/csqtt/"+name+"\"")) {
			result["fw4_missing_full_includes"] = false
		}
	}
	cmd = exec.CommandContext(ctx, "/usr/sbin/nft", "-c", "-f", "-")
	cmd.Stdin = bytes.NewReader(rules)
	output, err := cmd.CombinedOutput()
	os.WriteFile(filepath.Join(dir, "nft-check.private.log"), output, 0600)
	result["native_check"] = err == nil
	if result["full_files_absent"] && result["fw4_has_hold"] && result["native_check"] {
		exitCode = 0
	}
}
