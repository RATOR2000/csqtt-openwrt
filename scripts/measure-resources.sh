#!/bin/sh
# Owner-invoked, read-only measurements; does not start traffic or cause faults.
# Usage: sh measure-resources.sh PID idle|auth|traffic|recovery [samples [seconds]]
set -eu
umask 077
fail() { printf '%s\n' "CSQTT measurement: $*" >&2; exit 1; }
[ "$#" -ge 2 ] && [ "$#" -le 4 ] || fail 'Expected PID scenario [samples [seconds]].'
MEASURE_PID=$1 MEASURE_SCENARIO=$2 MEASURE_SAMPLES=${3:-60} MEASURE_INTERVAL=${4:-5}
case "$MEASURE_PID:$MEASURE_SAMPLES:$MEASURE_INTERVAL" in *[!0-9:]*|:*|*::*|*:) fail 'Numeric arguments required.' ;; esac
[ "$MEASURE_PID" -ge 1 ] && [ "$MEASURE_PID" -le 4194304 ] || fail 'PID out of bounds.'
[ "$MEASURE_SAMPLES" -ge 2 ] && [ "$MEASURE_SAMPLES" -le 720 ] || fail 'Samples must be 2..720.'
[ "$MEASURE_INTERVAL" -ge 1 ] && [ "$MEASURE_INTERVAL" -le 60 ] || fail 'Interval must be 1..60 seconds.'
case "$MEASURE_SCENARIO" in idle|auth|traffic|recovery) ;; *) fail 'Unknown measurement scenario.' ;; esac
for TOOL in awk readlink sleep; do command -v "$TOOL" >/dev/null || fail "Missing tool: $TOOL"; done
MEASURE_PROC="/proc/$MEASURE_PID"
identity() {
    [ "$(readlink "$MEASURE_PROC/exe" 2>/dev/null)" = /usr/bin/csqtt-client ] || return 1
    # Kernel TGID leader stat; never read or print the private command line.
    awk '{ sub(/^.*\) /, ""); if (NF < 22 || $20 !~ /^[0-9]+$/) exit 1; print $20 }' \
        "$MEASURE_PROC/task/$MEASURE_PID/stat" 2>/dev/null
}
MEASURE_START=$(identity) || fail 'Expected the installed CSQTT executable and live TGID.'
[ -n "$MEASURE_START" ] || fail 'Missing process identity.'
MEASURE_N=0
while [ "$MEASURE_N" -lt "$MEASURE_SAMPLES" ]; do
    [ "$(identity)" = "$MEASURE_START" ] || fail 'Process changed; measurement incomplete.'
    MEASURE_STATUS=$(awk '$1=="VmRSS:" { rss=$2 } $1=="VmHWM:" { hwm=$2 }
        END { if (rss !~ /^[0-9]+$/ || hwm !~ /^[0-9]+$/) exit 1; print rss, hwm }' "$MEASURE_PROC/status") || fail 'Missing process memory.'
    MEASURE_TICKS=$(awk '{ sub(/^.*\) /, ""); if ($12 !~ /^[0-9]+$/ || $13 !~ /^[0-9]+$/) exit 1; printf "%.0f", $12+$13 }' "$MEASURE_PROC/task/$MEASURE_PID/stat") || fail 'Missing process CPU counters.'
    MEASURE_HOST=$(awk '$1=="cpu" { n=0; for (i=2;i<=9 && i<=NF;i++) n+=$i; printf "%.0f",n; found=1; exit } END { if (!found) exit 1 }' /proc/stat) || fail 'Missing host CPU counters.'
    MEASURE_UPTIME=$(awk 'NR==1 && $1 ~ /^[0-9]+\.[0-9]+$/ { printf "%.0f",$1*100; ok=1 } END { if (!ok) exit 1 }' /proc/uptime) || fail 'Missing boot clock.'
    MEASURE_AVAILABLE=$(awk '$1=="MemAvailable:" && $2 ~ /^[0-9]+$/ { print $2; ok=1; exit } END { if (!ok) exit 1 }' /proc/meminfo) || fail 'Missing available memory.'
    [ "$(identity)" = "$MEASURE_START" ] || fail 'Process changed during sample; measurement incomplete.'
    set -- $MEASURE_STATUS
    printf '{"schema":1,"evidence":"resource_sample","scenario":"%s","pid":%s,"startticks":"%s","uptime_cs":%s,"rss_kib":%s,"hwm_kib":%s,"cpu_ticks":%s,"host_cpu_ticks":%s,"mem_available_kib":%s}\n' \
        "$MEASURE_SCENARIO" "$MEASURE_PID" "$MEASURE_START" "$MEASURE_UPTIME" "$1" "$2" "$MEASURE_TICKS" "$MEASURE_HOST" "$MEASURE_AVAILABLE"
    MEASURE_N=$((MEASURE_N + 1))
    [ "$MEASURE_N" -ge "$MEASURE_SAMPLES" ] || sleep "$MEASURE_INTERVAL"
done
