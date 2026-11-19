#!/bin/zsh
# Battle AI arena control.  ./arena.sh new | stop | sh a|b
# new = throw away the old arena and start a fresh one (the "snapshot reset").
N=battle-arena
case $1 in
  new)  docker rm -f $N >/dev/null 2>&1
        docker run -d --name $N --hostname arena --network none --cap-drop ALL \
          --cap-add CHOWN --cap-add FOWNER --cap-add DAC_OVERRIDE --cap-add SETUID --cap-add SETGID \
          --security-opt no-new-privileges --pids-limit 200 --memory 512m --cpus 2 battle-ai-arena >/dev/null && echo "fresh arena up" ;;
  stop) docker rm -f $N >/dev/null && echo "arena gone" ;;
  sh)   docker exec -it -u fighter_$2 -w /home/fighter_$2 $N bash ;;
esac
