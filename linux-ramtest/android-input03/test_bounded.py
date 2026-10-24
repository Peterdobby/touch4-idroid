#!/usr/bin/env python3
"""Run the exact shell supervisor with harmless host commands in temp files."""
from pathlib import Path
import json,os,subprocess,sys,tempfile,time,shlex
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OUT=ROOT/'saved/build/T4_ANDROID_INPUT_03'
with tempfile.TemporaryDirectory(prefix='t4-watch-test-') as tmp:
 t=Path(tmp);bb=t/'bb';bb.write_text('#!/bin/sh\ncmd=$1\nshift\ncase "$cmd" in kill) exec /bin/kill "$@";; sleep) exec /bin/sleep "$@";; *) exit 99;; esac\n');bb.chmod(0o755)
 header='bb='+shlex.quote(str(bb))+'\nheartbeat=0\npulse_input() { heartbeat=$((heartbeat+1)); }\n. '+shlex.quote(str(HERE/'t4-watch-bounded.sh'))+'\n'
 cases=[]
 for tag,limit,args,expected in [('success',3,['/bin/sh','-c','printf ok'],0),('failure',3,['/bin/sh','-c','exit 7'],7),('hung',1,[sys.executable,'-c','import os,signal,time;print(os.getpid(),flush=True);signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(30)'],124)]:
  output=t/(tag+'.log')
  script=header+'run_bounded '+str(limit)+' '+shlex.quote(str(output))+' '+shlex.join(args)+'\nresult=$?\necho "result=$result heartbeat=$heartbeat timeout=$any_timeout pid=$command_pid"\n'
  start=time.monotonic();response=subprocess.check_output(['/bin/sh','-c',script],text=True,timeout=9);duration=time.monotonic()-start
  values=dict(s.split('=',1) for s in response.split());assert int(values['result'])==expected and values['pid']=='',response
  if tag=='hung':
   assert duration<5 and values['timeout']=='1' and int(values['heartbeat'])>=2 and 'T4_COMMAND_TIMEOUT' in output.read_text()
   pid=int(output.read_text().splitlines()[0])
   try:os.kill(pid,0)
   except ProcessLookupError:pass
   else:raise AssertionError('timed out child still alive')
  else:assert values['timeout']=='0'
  cases.append({'case':tag,'result':expected,'heartbeat':int(values['heartbeat']),'seconds':round(duration,2)})
 # Watch cancellation also cleans up only its own child.
 pidfile=t/'child.pid';script=header+"trap 'stop_watch_child; exit 0' INT TERM\n"+'run_bounded 30 '+shlex.quote(str(t/'cancel.log'))+' '+shlex.join([sys.executable,'-c',f'import os,time;open({str(pidfile)!r},"w").write(str(os.getpid()));time.sleep(30)'])+'\n'
 p=subprocess.Popen(['/bin/sh','-c',script],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 deadline=time.monotonic()+3
 while not pidfile.exists() and time.monotonic()<deadline:time.sleep(.03)
 assert pidfile.exists();pid=int(pidfile.read_text());p.terminate();assert p.wait(timeout=4)==0
 try:os.kill(pid,0)
 except ProcessLookupError:pass
 else:raise AssertionError('cancelled watch child still alive')
report={'exact_shell_supervisor_cases':cases,'TERM_ignored_child_killed_and_reaped':True,'watch_cancel_child_cleanup':True,'no_hardware_calls':True,'hardware':'pending'}
(OUT/'bounded-script-test.json').write_text(json.dumps(report,indent=2)+'\n');print('BOUNDED_SCRIPT_PASSED: success, real failure, timeout, continued heartbeat, cancellation cleanup')
