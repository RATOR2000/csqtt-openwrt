package main

import (
	"encoding/binary"
	"runtime"
	"syscall"
	"testing"
)

func answerFixture(id uint16) []byte {
	p := makeQuery(id)
	binary.BigEndian.PutUint16(p[2:4], 0x8180)
	binary.BigEndian.PutUint16(p[6:8], 1)
	return append(p, []byte{0xc0, 0x0c, 0, 1, 0, 1, 0, 0, 0, 60, 0, 4, 192, 0, 2, 1}...)
}

func TestPositiveAnswer(t *testing.T) {
	if n, ok := parseAnswer(answerFixture(1234), 1234); !ok || n != 1 {
		t.Fatalf("valid answer rejected")
	}
}

func TestRejectedAnswers(t *testing.T) {
	tests := []struct {
		name   string
		change func([]byte) []byte
	}{
		{"transaction ID", func(p []byte) []byte { p[1] ^= 1; return p }},
		{"response bit", func(p []byte) []byte { p[2] &^= 0x80; return p }},
		{"question count", func(p []byte) []byte { p[5] = 2; return p }},
		{"rcode", func(p []byte) []byte { p[3] = 0x83; return p }},
		{"zero answers", func(p []byte) []byte { p[7] = 0; return p }},
		{"truncated header", func(p []byte) []byte { return p[:11] }},
		{"truncated answer", func(p []byte) []byte { return p[:len(p)-1] }},
		{"bad address length", func(p []byte) []byte { p[len(p)-5] = 3; return p }},
		{"bad question", func(p []byte) []byte { p[13] = 'x'; return p }},
		{"pointer cycle", func(p []byte) []byte { p[12] = 0xc0; p[13] = 0x0c; return p }},
		{"trailing garbage", func(p []byte) []byte { return append(p, 0) }},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if _, ok := parseAnswer(test.change(answerFixture(1234)), 1234); ok {
				t.Fatalf("invalid answer accepted")
			}
		})
	}
}

func TestNoReplyAndBadConfigurationAreDistinct(t *testing.T) {
	r := run([]string{"-server", "invalid", "-expect", "blocked"})
	if r.ConfigValid || r.ConnectionAttempted || r.NoDNSReply || r.BlockedCandidate || r.ExpectationMet {
		t.Fatal("configuration error treated as no reply")
	}
}

func TestConnectionRefusalClassification(t *testing.T) {
	r := result{}
	networkError(&r, syscall.ECONNREFUSED)
	if !r.ConnectionRefused || r.Timeout {
		t.Fatal("refusal classification failed")
	}
	if runtime.GOOS == "windows" {
		r = result{}
		networkError(&r, syscall.Errno(10061))
		if !r.ConnectionRefused || r.Timeout {
			t.Fatal("Winsock refusal classification failed")
		}
	}
}
