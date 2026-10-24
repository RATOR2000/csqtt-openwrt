// Ignored boot7 DNS probe. A no-reply result needs external ingress counters;
// this program cannot independently prove that a firewall blocked traffic.
package main

import (
	"crypto/rand"
	"encoding/binary"
	"encoding/json"
	"errors"
	"flag"
	"io"
	"net"
	"os"
	"runtime"
	"strconv"
	"strings"
	"syscall"
	"time"
)

const queryName = "example.com"

type result struct {
	Protocol                    string `json:"protocol"`
	Expectation                 string `json:"expectation"`
	Outcome                     string `json:"outcome"`
	Port                        int    `json:"port"`
	DeadlineMS                  int    `json:"deadline_ms"`
	ConfigValid                 bool   `json:"config_valid"`
	ConnectionAttempted         bool   `json:"connection_attempted"`
	ProbeAttempts               int    `json:"probe_attempts"`
	Connected                   bool   `json:"connected"`
	ConnectError                bool   `json:"connect_error"`
	ConnectionRefused           bool   `json:"connection_refused"`
	QueryWritten                bool   `json:"query_written"`
	QueriesWritten              int    `json:"queries_written"`
	WriteError                  bool   `json:"write_error"`
	ReadError                   bool   `json:"read_error"`
	Timeout                     bool   `json:"timeout"`
	BytesWritten                int    `json:"bytes_written"`
	BytesReceived               int    `json:"bytes_received"`
	DNSReplyReceived            bool   `json:"dns_reply_received"`
	NoDNSReply                  bool   `json:"no_dns_reply"`
	ValidAnswer                 bool   `json:"valid_answer"`
	AnswerCount                 int    `json:"answer_count"`
	BlockedCandidate            bool   `json:"blocked_candidate"`
	RequiresIngressCounterProof bool   `json:"requires_ingress_counter_proof"`
	StandaloneBlockingProof     bool   `json:"standalone_blocking_proof"`
	ExpectationMet              bool   `json:"expectation_met"`
}

func networkError(r *result, err error) {
	var e net.Error
	r.Timeout = errors.As(err, &e) && e.Timeout()
	r.ConnectionRefused = errors.Is(err, syscall.ECONNREFUSED) ||
		(runtime.GOOS == "windows" && errors.Is(err, syscall.Errno(10061))) // WSAECONNREFUSED
}

// readName validates labels and compression bounds, including pointer cycles.
func readName(packet []byte, start int) (string, int, bool) {
	pos, next, expanded := start, -1, 0
	labels := []string{}
	seen := make(map[int]bool)
	for steps := 0; steps < 128; steps++ {
		if pos < 0 || pos >= len(packet) || seen[pos] {
			return "", 0, false
		}
		seen[pos] = true
		n := int(packet[pos])
		if n == 0 {
			if next < 0 {
				next = pos + 1
			}
			return strings.Join(labels, "."), next, expanded <= 254
		}
		if n&0xc0 == 0xc0 {
			if pos+1 >= len(packet) {
				return "", 0, false
			}
			if next < 0 {
				next = pos + 2
			}
			pos = (n&0x3f)<<8 | int(packet[pos+1])
			continue
		}
		if n&0xc0 != 0 || n > 63 || pos+1+n >= len(packet) {
			return "", 0, false
		}
		labels = append(labels, string(packet[pos+1:pos+1+n]))
		expanded += n + 1
		pos += n + 1
	}
	return "", 0, false
}

// Positive control requires a complete response to our A/IN question, matching
// ID, QR, opcode, QD=1, no truncation, RCODE=0, and at least one answer record.
func parseAnswer(packet []byte, id uint16) (int, bool) {
	if len(packet) < 12 || binary.BigEndian.Uint16(packet[:2]) != id {
		return 0, false
	}
	flags := binary.BigEndian.Uint16(packet[2:4])
	if flags&0x8000 == 0 || flags&0x7800 != 0 || flags&0x0200 != 0 || flags&0x000f != 0 ||
		binary.BigEndian.Uint16(packet[4:6]) != 1 {
		return 0, false
	}
	answers := int(binary.BigEndian.Uint16(packet[6:8]))
	if answers < 1 {
		return 0, false
	}
	name, pos, ok := readName(packet, 12)
	if !ok || !strings.EqualFold(name, queryName) || pos+4 > len(packet) ||
		binary.BigEndian.Uint16(packet[pos:pos+2]) != 1 || binary.BigEndian.Uint16(packet[pos+2:pos+4]) != 1 {
		return 0, false
	}
	pos += 4
	records := answers + int(binary.BigEndian.Uint16(packet[8:10])) + int(binary.BigEndian.Uint16(packet[10:12]))
	for i := 0; i < records; i++ {
		_, end, valid := readName(packet, pos)
		if !valid || end+10 > len(packet) {
			return 0, false
		}
		kind := binary.BigEndian.Uint16(packet[end : end+2])
		length := int(binary.BigEndian.Uint16(packet[end+8 : end+10]))
		if end+10+length > len(packet) || (kind == 1 && length != 4) || (kind == 28 && length != 16) {
			return 0, false
		}
		pos = end + 10 + length
	}
	return answers, pos == len(packet)
}

func makeQuery(id uint16) []byte {
	q := make([]byte, 12)
	binary.BigEndian.PutUint16(q[:2], id)
	binary.BigEndian.PutUint16(q[2:4], 0x0100)
	binary.BigEndian.PutUint16(q[4:6], 1)
	return append(q, []byte("\x07example\x03com\x00\x00\x01\x00\x01")...)
}

func run(args []string) result {
	r := result{Protocol: "udp", Expectation: "answer", Outcome: "config_error", DeadlineMS: 1500}
	f := flag.NewFlagSet("dns-probe", flag.ContinueOnError)
	f.SetOutput(io.Discard)
	server := f.String("server", "", "IPv4 destination")
	port := f.Int("port", 53, "53 or 5400")
	protocol := f.String("protocol", "udp", "udp or tcp")
	name := f.String("name", queryName, "fixed example.com question")
	expect := f.String("expect", "answer", "answer or blocked")
	if f.Parse(args) != nil || f.NArg() != 0 {
		return r
	}
	if *protocol != "udp" && *protocol != "tcp" {
		return r
	}
	r.Protocol = *protocol
	if *expect != "answer" && *expect != "blocked" {
		return r
	}
	r.Expectation = *expect
	r.RequiresIngressCounterProof = *expect == "blocked"
	if *port != 53 && *port != 5400 {
		return r
	}
	r.Port = *port
	ip := net.ParseIP(*server)
	if ip == nil || ip.To4() == nil || ip.String() != *server || *name != queryName {
		return r
	}
	r.ConfigValid = true
	var randomID [2]byte
	if _, err := rand.Read(randomID[:]); err != nil {
		r.Outcome = "random_error"
		return r
	}
	id := binary.BigEndian.Uint16(randomID[:])
	query := makeQuery(id)
	deadline := time.Now().Add(1500 * time.Millisecond)
	r.ConnectionAttempted, r.ProbeAttempts = true, 1
	dialer := net.Dialer{Deadline: deadline}
	c, err := dialer.Dial(*protocol+"4", net.JoinHostPort(*server, strconv.Itoa(*port)))
	if err != nil {
		r.Outcome, r.ConnectError = "connect_error", true
		networkError(&r, err)
		r.NoDNSReply = true
		// A refused/timed-out TCP SYN can be a firewall rejection. It is only a
		// candidate, with attempts=1 and queries_written=0; ingress must be observed.
		r.BlockedCandidate = *protocol == "tcp" && (r.ConnectionRefused || r.Timeout)
		r.ExpectationMet = *expect == "blocked" && r.BlockedCandidate
		return r
	}
	defer c.Close()
	r.Connected = true
	if err = c.SetDeadline(deadline); err != nil {
		r.Outcome = "deadline_error"
		return r
	}
	if *protocol == "tcp" {
		frame := make([]byte, 2, len(query)+2)
		binary.BigEndian.PutUint16(frame, uint16(len(query)))
		query = append(frame, query...)
	}
	for r.BytesWritten < len(query) {
		n, err := c.Write(query[r.BytesWritten:])
		r.BytesWritten += n
		if err != nil || n == 0 {
			r.Outcome, r.WriteError = "write_error", true
			if err != nil {
				networkError(&r, err)
			}
			r.NoDNSReply = true
			return r
		}
	}
	r.QueryWritten, r.QueriesWritten = true, 1
	var reply []byte
	if *protocol == "udp" {
		buffer := make([]byte, 65535)
		n, err := c.Read(buffer)
		r.BytesReceived = n
		r.DNSReplyReceived = err == nil || n > 0
		reply = buffer[:n]
		if err != nil {
			r.ReadError = true
			networkError(&r, err)
		}
	} else {
		var prefix [2]byte
		n, err := io.ReadFull(c, prefix[:])
		r.BytesReceived = n
		r.DNSReplyReceived = n > 0
		if err != nil {
			r.ReadError = true
			networkError(&r, err)
		} else {
			length := int(binary.BigEndian.Uint16(prefix[:]))
			if length >= 12 {
				reply = make([]byte, length)
				n, err = io.ReadFull(c, reply)
				r.BytesReceived += n
				if err != nil {
					r.ReadError = true
					networkError(&r, err)
					reply = reply[:n]
				}
			}
		}
	}
	r.NoDNSReply = !r.DNSReplyReceived
	if r.ReadError {
		r.Outcome = "read_error"
		if r.Timeout {
			r.Outcome = "read_timeout"
		}
		if r.DNSReplyReceived {
			r.Outcome = "incomplete_reply"
		}
	} else {
		r.AnswerCount, r.ValidAnswer = parseAnswer(reply, id)
		r.Outcome = "invalid_reply"
		if r.ValidAnswer {
			r.Outcome = "answer"
		}
	}
	r.BlockedCandidate = r.QueryWritten && r.NoDNSReply && r.ReadError
	r.ExpectationMet = (*expect == "answer" && r.ValidAnswer) || (*expect == "blocked" && r.BlockedCandidate)
	return r
}

func main() {
	r := run(os.Args[1:])
	_ = json.NewEncoder(os.Stdout).Encode(r)
	if !r.ExpectationMet {
		os.Exit(1)
	}
}
