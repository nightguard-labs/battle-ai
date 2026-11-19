#!/usr/bin/env python3
"""Turn a match/replay page into a social video WITH the game's real sound, at 1x speed (hands-free, headless Chrome).
  python3 make_clip.py fights/match-X/match.html clips/name.mp4
How: 1) fast-forward the page on a virtual clock to find when it ends; 2) same clock, but the speaker is swapped for a
recorder (OfflineAudioContext) so every sound lands at the exact time; 3) one screenshot per 1/8 s; 4) ffmpeg joins them."""
import json, os, re, shutil, subprocess, sys, time
SRC, OUT = sys.argv[1], sys.argv[2]
D = os.path.dirname(os.path.abspath(__file__)); W = f"{D}/clipwork"; shutil.rmtree(W, ignore_errors=True); os.makedirs(f"{W}/f")
CH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
base = open(SRC).read()
auto_js = "<style>.bar i{transition:none!important}</style><script>muted=true;musicOn=false;speed=1;setTimeout(()=>$('play').click(),300)</script></body>"
open(f"{W}/auto.html", "w").write(base.replace("</body>", auto_js))
probe = base.replace("</body>", "<script>muted=true;musicOn=false;speed=1;const __t0=performance.now();setTimeout(()=>$('play').click(),300);"
    "setInterval(()=>{if($('turn').textContent==='MATCH OVER'||(/WINS|DRAW/.test($('score').textContent)&&!(R&&DATA&&DATA.legs)))if(!document.body.dataset.end)document.body.dataset.end=Math.round(performance.now()-__t0)},50)</script></body>")
open(f"{W}/probe.html", "w").write(probe)
dom = subprocess.run([CH, "--headless=new", "--disable-gpu", "--virtual-time-budget=400000", "--dump-dom", f"file://{W}/probe.html"],
                     capture_output=True, text=True).stdout
end = int(re.search(r'data-end="(\d+)"', dom).group(1)) + 4500          # hold on the verdict
secs = end / 1000; print(f"ends at {secs:.1f}s", flush=True)
rec_head = """<script>
const __OFF=new OfflineAudioContext(2,44100*%d,44100);let __T0=null;
window.AudioContext=window.webkitAudioContext=function(){return new Proxy(__OFF,{get(t,p){if(p==="currentTime")return (performance.now()-__T0)/1000;if(p==="state")return "running";if(p==="resume")return ()=>Promise.resolve();const v=t[p];return typeof v==="function"?v.bind(t):v}})};
function __wav(b){const n=b.length,ch=2,buf=new ArrayBuffer(44+n*ch*2),v=new DataView(buf);let o=0;const w=s=>{for(const c of s)v.setUint8(o++,c.charCodeAt(0))};
 w("RIFF");v.setUint32(o,36+n*ch*2,true);o+=4;w("WAVEfmt ");v.setUint32(o,16,true);o+=4;v.setUint16(o,1,true);o+=2;v.setUint16(o,ch,true);o+=2;v.setUint32(o,44100,true);o+=4;v.setUint32(o,44100*ch*2,true);o+=4;v.setUint16(o,ch*2,true);o+=2;v.setUint16(o,16,true);o+=2;w("data");v.setUint32(o,n*ch*2,true);o+=4;
 const L=b.getChannelData(0),R=b.getChannelData(1);for(let k=0;k<n;k++){for(const x of [L[k],R[k]]){v.setInt16(o,Math.max(-1,Math.min(1,x))*32767,true);o+=2}}return buf}
</script>""" % (int(secs) + 3)
rec = (rec_head + base) if "<head>" not in base else base.replace("<head>", "<head>" + rec_head, 1)
rec = rec.replace("</body>", "<script>__T0=performance.now();muted=false;musicOn=true;speed=1;setTimeout(()=>$('play').click(),300);"
    f"setTimeout(()=>{{__OFF.startRendering().then(b=>fetch('/wav',{{method:'POST',body:__wav(b)}}));fetch('/hold')}},{end})</script></body>")
open(f"{W}/rec.html", "w").write(rec)
subprocess.run("lsof -ti tcp:8791 | xargs kill 2>/dev/null", shell=True)
srv = subprocess.Popen([sys.executable, f"{D}/clip_srv.py", W], stdout=open(f"{W}/srv.log","w"), stderr=subprocess.STDOUT); time.sleep(1)
subprocess.run([CH, "--headless=new", "--disable-gpu", "--mute-audio", f"--user-data-dir={W}/prof-rec", f"--virtual-time-budget={end + 20000}",
                "--dump-dom", "http://127.0.0.1:8791/rec.html"], capture_output=True)
time.sleep(2); srv.kill()
if not os.path.exists(f"{W}/audio.wav"): sys.exit("audio capture failed: " + open(f"{W}/srv.log").read()[-800:])
print("audio ok", flush=True)
n = int((end - 200) / 125) + 1
env = dict(os.environ, W=W, CH=CH)                                          # short names: BSD xargs -I caps the command at 255 bytes
subprocess.run(f"seq 0 {n - 1} | xargs -P 8 -I{{}} sh -c " + "'" + 't=$(( {} * 125 + 200 )); "$CH" --headless=new --disable-gpu --hide-scrollbars '
               '--mute-audio --user-data-dir=$W/prof-$(( {} % 8 )) --window-size=900,700 --virtual-time-budget=$t '
               '--screenshot=$W/f/$(printf %05d {}).png file://$W/auto.html >/dev/null 2>&1' + "'", shell=True, env=env)
print("frames", len(os.listdir(f"{W}/f")), flush=True)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "8", "-i", f"{W}/f/%05d.png", "-ss", "0.2", "-i", f"{W}/audio.wav",
                "-map", "0:v", "-map", "1:a", "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-crf", "20", "-c:a", "aac", "-b:a", "160k",
                "-af", "loudnorm=I=-16:TP=-1.5", "-shortest", "-movflags", "+faststart", OUT], check=True)
shutil.rmtree(W, ignore_errors=True)
print("clip:", OUT)
