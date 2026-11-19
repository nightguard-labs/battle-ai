#!/bin/zsh
# Battle AI escape tests: everything in the "should FAIL" group must fail, or the cage is not safe.
X="docker exec -u fighter_a -w /home/fighter_a battle-arena bash -c"
ok=0; bad=0
must_fail() { if eval "$X \"$2\"" >/dev/null 2>&1; then echo "❌ ESCAPE: $1"; bad=$((bad+1)); else echo "✅ blocked: $1"; ok=$((ok+1)); fi }
must_work() { if eval "$X \"$2\"" >/dev/null 2>&1; then echo "✅ works:   $1"; ok=$((ok+1)); else echo "❌ BROKEN:  $1"; bad=$((bad+1)); fi }
echo "--- reach the internet / your Mac (must all be blocked)"
must_fail "internet (python to 1.1.1.1:443)"       "python3 -c 'import socket;socket.create_connection((\\\"1.1.1.1\\\",443),3)'"
must_fail "DNS lookup (example.com)"               "python3 -c 'import socket;socket.gethostbyname(\\\"example.com\\\")'"
must_fail "your Mac via host.docker.internal:11442 (twins)" "python3 -c 'import socket;socket.create_connection((\\\"host.docker.internal\\\",11442),3)'"
must_fail "Docker gateway 192.168.65.254:11442"    "python3 -c 'import socket;socket.create_connection((\\\"192.168.65.254\\\",11442),3)'"
must_fail "a network route out (routing table)"   "grep -v Iface /proc/net/route | grep ."
must_fail "an IPv6 route out"                     "grep -v ' lo$' /proc/net/ipv6_route | grep ."
must_fail "any interface switched on besides lo"  "for i in /sys/class/net/*; do [ \\$(basename \\$i) = lo ] && continue; grep -q up \\$i/operstate 2>/dev/null && echo up; done | grep ."
echo "--- see your Mac's files or control Docker (must all be blocked)"
must_fail "your Mac's /Users folder"               "ls /Users"
must_fail "the Docker control socket"              "ls /var/run/docker.sock"
must_fail "become root (su)"                       "su -c id root </dev/null"
must_fail "root's files (/root)"                   "ls /root"
echo "--- fight rules"
must_work "EDIT the other fighter's personality"   "echo '# touched' >> /arena/b/persona.md"
must_fail "DELETE the other's personality"         "rm -f /arena/b/persona.md && ! test -e /arena/b/persona.md"
must_fail "LOCK the other's file (chmod)"          "chmod 600 /arena/b/persona.md"
must_fail "RENAME the other's file"                "mv /arena/b/notes.md /arena/b/x"
must_fail "read the other's private stash"         "ls /home/fighter_b"
must_work "save a backup in own stash"             "cp /arena/a/persona.md ~/backup.md"
echo; echo "result: $ok ok, $bad problems"
