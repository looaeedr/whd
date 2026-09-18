#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import shutil
import stat
import subprocess
import sys
import time
from datetime import datetime

FLOW="/storage/docker/app/nodered/flows.json"
HTML="/storage/docker/share/data/bills/bill_manager.html"
CONTAINER="nodered"
stamp=datetime.now().strftime("%Y%m%d-%H%M%S")
flow_bak=FLOW+".bak-authfix-"+stamp
html_bak=HTML+".bak-authfix-"+stamp

def run(*args, check=True):
    return subprocess.run(args, text=True, capture_output=True, check=check)

def replace_preserve(tmp, dst):
    st=os.stat(dst)
    os.replace(tmp,dst)
    os.chown(dst,st.st_uid,st.st_gid)
    os.chmod(dst,stat.S_IMODE(st.st_mode))

def save_json(path,obj):
    tmp=path+".authfix.tmp"
    with open(tmp,"w",encoding="utf-8") as f:
        json.dump(obj,f,ensure_ascii=False,separators=(",",":"))
    with open(tmp,encoding="utf-8") as f:
        json.load(f)
    replace_preserve(tmp,path)

def start():
    run("docker","start",CONTAINER,check=False)

def stop():
    r=run("docker","stop",CONTAINER,check=False)
    if r.returncode != 0:
        raise RuntimeError("docker stop failed: "+(r.stderr or r.stdout))

for p in (FLOW,HTML):
    if not os.path.isfile(p):
        raise SystemExit("ERROR missing: "+p)

shutil.copy2(FLOW,flow_bak)
shutil.copy2(HTML,html_bak)
print("backup_flow =",flow_bak)
print("backup_html =",html_bak)

try:
    with open(FLOW,encoding="utf-8") as f:
        flows=json.load(f)

    result=next((n for n in flows if n.get("id")=="bills_atomic_result"),None)
    writer=next((n for n in flows if n.get("id")=="write_bills_file"),None)
    mover=next((n for n in flows if n.get("id")=="bills_atomic_mv"),None)
    response=next((n for n in flows if n.get("id")=="http_resp_post"),None)

    if not all((result,writer,mover,response)):
        raise RuntimeError("atomic save nodes incomplete")

    result["func"] = """let code = 0;

if (typeof msg.payload === "number") {
    code = msg.payload;
} else if (msg.payload && typeof msg.payload.code !== "undefined") {
    code = Number(msg.payload.code);
} else if (msg.rc && typeof msg.rc.code !== "undefined") {
    code = Number(msg.rc.code);
}

if (code === 0) {
    msg.statusCode = 200;
    msg.payload = { ok: true };
} else {
    msg.statusCode = 500;
    msg.payload = {
        ok: false,
        error: "atomic save failed",
        code: code
    };
}

return msg;"""

    if writer.get("filename") != "/storage/docker/share/data/bills/bills.tmp":
        raise RuntimeError("writer is not using bills.tmp")
    if writer.get("wires") != [["bills_atomic_mv"]]:
        raise RuntimeError("writer wire is wrong")
    if mover.get("wires",[[],[],[]])[2] != ["bills_atomic_result"]:
        raise RuntimeError("mover rc wire is wrong")
    if result.get("wires") != [["http_resp_post"]]:
        raise RuntimeError("result response wire is wrong")

    with open(HTML,encoding="utf-8") as f:
        html=f.read()

    old='''<label>帳號</label><input id="user" value="bills" autocomplete="username">
<label>密碼</label><input id="pass" type="password" autocomplete="current-password">'''
    new='''<label>帳號</label><input id="user" name="username" value="bills" autocomplete="username">
<label>密碼</label><input id="pass" name="password" type="password" autocomplete="current-password">'''

    if old in html:
        html=html.replace(old,new,1)

    old_auth='''function auth(){
  const u=$("user").value.trim(),p=$("pass").value;
  if(!u||!p)throw new Error("請輸入 bills 帳號與密碼");
  const bytes=new TextEncoder().encode(u+":"+p);
  let s="";
  for(const b of bytes)s+=String.fromCharCode(b);
  return btoa(s);
}'''

    new_auth='''function auth(){
  const userEl=document.getElementById("user");
  const passEl=document.getElementById("pass");

  let u=(userEl && userEl.value ? userEl.value : "").trim();
  let p=(passEl && passEl.value ? passEl.value : "");

  if(!u){
    u="bills";
    if(userEl)userEl.value=u;
  }

  if(!p){
    p=window.prompt("請輸入 bills 寫入密碼") || "";
    if(passEl && p)passEl.value=p;
  }

  if(!p){
    throw new Error("未取得 bills 密碼");
  }

  const bytes=new TextEncoder().encode(u+":"+p);
  let s="";
  for(const b of bytes)s+=String.fromCharCode(b);
  return btoa(s);
}'''

    if old_auth not in html:
        if "function auth(){" in html and "window.prompt(\"請輸入 bills 寫入密碼\")" in html:
            pass
        else:
            raise RuntimeError("current auth() block not recognized")
    else:
        html=html.replace(old_auth,new_auth,1)

    if 'name="username"' not in html or 'name="password"' not in html:
        raise RuntimeError("auth input names missing")
    if 'window.prompt("請輸入 bills 寫入密碼")' not in html:
        raise RuntimeError("auth fallback missing")

    print("candidate_atomic_func =", "\\n" not in result["func"] and "\n" in result["func"])
    print("candidate_auth_fallback = True")

    stop()

    save_json(FLOW,flows)

    tmp=HTML+".authfix.tmp"
    with open(tmp,"w",encoding="utf-8") as f:
        f.write(html)
    replace_preserve(tmp,HTML)

    start()
    time.sleep(4)

    with open(FLOW,encoding="utf-8") as f:
        live=json.load(f)
    r=next(n for n in live if n.get("id")=="bills_atomic_result")

    print("atomic_real_newlines =", "\n" in r.get("func",""))
    print("atomic_literal_backslash_n =", "\\n" in r.get("func",""))

    ps=run("docker","ps","--filter","name=nodered","--format","{{.Status}}",check=False)
    print("nodered =", (ps.stdout or "").strip())

    logs=run("docker","logs","--since","15s","nodered",check=False)
    bad=[]
    for line in ((logs.stdout or "")+"\n"+(logs.stderr or "")).splitlines():
        low=line.lower()
        if "bills_atomic_result" in low or ("syntaxerror" in low and "function" in low):
            bad.append(line)

    if bad:
        print("NODE_RED_ERRORS:")
        for line in bad[-20:]:
            print(line)
        raise RuntimeError("Node-RED reported function compile errors")

    print("=== AUTH + ATOMIC HOTFIX OK ===")

except Exception:
    print("=== RESTORE ===",file=sys.stderr)
    shutil.copy2(flow_bak,FLOW)
    shutil.copy2(html_bak,HTML)
    start()
    raise
