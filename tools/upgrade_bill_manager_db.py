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

FLOW = "/storage/docker/app/nodered/flows.json"
HTML = "/storage/docker/share/data/bills/bill_manager.html"
BILLS = "/storage/docker/share/data/bills/bills.json"
CONTAINER = "nodered"

stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
backups = {
    FLOW: FLOW + ".bak-billdb-" + stamp,
    HTML: HTML + ".bak-billdb-" + stamp,
    BILLS: BILLS + ".bak-billdb-" + stamp,
}

def sh(*args, check=True):
    return subprocess.run(args, check=check, text=True, capture_output=True)

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def dump_json_atomic(path, obj, indent=None):
    tmp = path + ".upgrade.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=indent, separators=None if indent else (",", ":"))
        if indent:
            f.write("\n")
    load_json(tmp)
    replace_preserve(tmp, path)

def replace_preserve(src, dst):
    st = os.stat(dst)
    os.replace(src, dst)
    os.chown(dst, st.st_uid, st.st_gid)
    os.chmod(dst, stat.S_IMODE(st.st_mode))

def node(flows, nid):
    return next((x for x in flows if x.get("id") == nid), None)

def start_nodered():
    sh("docker", "start", CONTAINER, check=False)

def stop_nodered():
    r = sh("docker", "stop", CONTAINER, check=False)
    if r.returncode != 0:
        raise RuntimeError("docker stop nodered failed: " + (r.stderr or r.stdout))

for path in (FLOW, HTML, BILLS):
    if not os.path.isfile(path):
        raise SystemExit("ERROR: missing file: " + path)

print("=== BACKUP ===")
for src, dst in backups.items():
    shutil.copy2(src, dst)
    print(dst)

try:
    print("=== PREPARE BILLS ===")
    bills = load_json(BILLS)
    if not isinstance(bills, list):
        raise RuntimeError("bills.json must be an array")

    for b in bills:
        if not isinstance(b, dict):
            raise RuntimeError("bill item must be an object")
        b.setdefault("amount", 0)
        b.setdefault("paid", False)
        b.setdefault("paid_at", "")
        b.setdefault("history", [])
        b.setdefault("last_notified", "")
        if not isinstance(b.get("history"), list):
            b["history"] = []
        if not isinstance(b.get("payment_methods"), list):
            b["payment_methods"] = []

    print("bill_count =", len(bills))

    print("=== PREPARE FLOWS ===")
    flows = load_json(FLOW)
    if not isinstance(flows, list):
        raise RuntimeError("flows.json must be an array")

    core = node(flows, "e7394ecf2e7dcb7b")
    current = node(flows, "c4de7e1dc5989247")
    write_node = node(flows, "write_bills_file")
    response_node = node(flows, "http_resp_post")

    if core is None:
        raise RuntimeError("current bill core e7394ecf2e7dcb7b not found")
    if current is None:
        raise RuntimeError("current schedule c4de7e1dc5989247 not found")
    if write_node is None or response_node is None:
        raise RuntimeError("/bills/save nodes not found")

    core["name"] = "Bill core v8 - notify + paid + amount"
    core["func"] = r'''if (msg.error) {
    node.error("read bills.json failed: " + msg.error.message);
    flow.set("bill_lock", false);
    return null;
}

let bills;
try {
    bills = JSON.parse(msg.payload);
} catch (e) {
    node.error("bills.json parse failed: " + e.message);
    flow.set("bill_lock", false);
    return null;
}

if (!Array.isArray(bills)) {
    node.error("bills.json must be an array");
    flow.set("bill_lock", false);
    return null;
}

const getLocalTS = () => {
    const d = new Date();
    const pad = n => String(n).padStart(2, "0");
    return d.getFullYear() + "-" +
        pad(d.getMonth() + 1) + "-" +
        pad(d.getDate()) + " " +
        pad(d.getHours()) + ":" +
        pad(d.getMinutes()) + ":" +
        pad(d.getSeconds());
};

const todayStr = getLocalTS().split(" ")[0];

function addMonthsSafe(dateStr, months) {
    let parts = String(dateStr || "").split("-").map(Number);
    let y = parts[0], m = parts[1], d = parts[2];
    if (!y || !m || !d) return null;

    const step = Math.max(1, Number(months) || 1);
    const totalMonths = (y * 12) + (m - 1) + step;
    const year = Math.floor(totalMonths / 12);
    const month = totalMonths % 12;
    const lastDay = new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
    const finalDay = Math.min(d, lastDay);

    return year + "-" +
        String(month + 1).padStart(2, "0") + "-" +
        String(finalDay).padStart(2, "0");
}

function dayDiff(fromDate, toDate) {
    const a = String(fromDate).split("-").map(Number);
    const b = String(toDate).split("-").map(Number);
    if (!a[0] || !a[1] || !a[2] || !b[0] || !b[1] || !b[2]) return null;

    const fromUtc = Date.UTC(a[0], a[1] - 1, a[2]);
    const toUtc = Date.UTC(b[0], b[1] - 1, b[2]);
    return Math.round((toUtc - fromUtc) / 86400000);
}

let modified = false;
let events = [];
let lineMessages = flow.get("pending_line_messages") || [];
if (!Array.isArray(lineMessages)) lineMessages = [];

bills.forEach(bill => {
    if (!bill || !bill.due_day) return;

    if (bill.amount === undefined || bill.amount === null) bill.amount = 0;
    if (bill.paid === undefined) bill.paid = false;
    if (!bill.paid_at) bill.paid_at = "";
    if (!Array.isArray(bill.history)) bill.history = [];
    if (!Array.isArray(bill.payment_methods)) bill.payment_methods = [];
    if (!bill.last_notified) bill.last_notified = "";

    while (bill.due_day < todayStr) {
        const oldDay = bill.due_day;
        const nextDay = addMonthsSafe(bill.due_day, bill.period || 1);

        if (!nextDay || nextDay === oldDay) {
            break;
        }

        bill.due_day = nextDay;
        bill.last_notified = "";
        bill.paid = false;
        bill.paid_at = "";
        bill.event_created = false;
        modified = true;

        events.push({
            event: "bill_rollover",
            name: bill.name,
            from: oldDay,
            to: bill.due_day,
            time: getLocalTS()
        });
    }

    if (bill.paid === true) {
        return;
    }

    const daysLeft = dayDiff(todayStr, bill.due_day);
    const notifyBefore = Math.max(0, Number(bill.notify_before || 0));

    if (daysLeft !== null && daysLeft >= 0 && daysLeft <= notifyBefore) {
        const lastTs = bill.last_notified || "";

        if (!lastTs.startsWith(todayStr)) {
            const dueText = daysLeft === 0
                ? "\u4eca\u65e5\u5230\u671f"
                : "\u9084\u6709 " + daysLeft + " \u5929\u5230\u671f";

            const amountText = Number(bill.amount || 0).toLocaleString();
            const methods = bill.payment_methods.length
                ? bill.payment_methods.join(", ")
                : "\u672a\u8a2d\u5b9a";

            lineMessages.push(
                "\ud83d\udcc5 \u3010\u5e33\u55ae\u63d0\u9192\u3011" + bill.name + " " + dueText + "\n" +
                "\u671f\u9650\uff1a" + bill.due_day + "\n" +
                "\u91d1\u984d\uff1aNT$" + amountText + "\n" +
                "\u65b9\u5f0f\uff1a" + methods
            );

            bill.last_notified = getLocalTS();
            modified = true;
        }
    }
});

if (modified || lineMessages.length > 0) {
    msg.payload = JSON.stringify(bills, null, 2);
    flow.set("pending_bill_events", events);
    flow.set("pending_line_messages", lineMessages);
    return msg;
}

flow.set("bill_lock", false);
return null;'''

    for nid in ("bill_flow_v4_inject", "bill_flow_v6_inject", "49b329c1e7bf16f6"):
        n = node(flows, nid)
        if n is not None:
            n["d"] = True

    current["d"] = False
    current["name"] = "Bill reminder 21:00"

    write_node["name"] = "Atomic 1 - write bills.tmp"
    write_node["filename"] = "/storage/docker/share/data/bills/bills.tmp"
    write_node["appendNewline"] = False
    write_node["createDir"] = True
    write_node["overwriteFile"] = "true"
    write_node["wires"] = [["bills_atomic_mv"]]

    response_node["statusCode"] = ""
    response_node["headers"] = {"content-type": "application/json"}

    flows = [x for x in flows if x.get("id") not in ("bills_atomic_mv", "bills_atomic_result")]

    flows.append({
        "id": "bills_atomic_mv",
        "type": "exec",
        "z": "bills_flow_group",
        "command": "mv /storage/docker/share/data/bills/bills.tmp /storage/docker/share/data/bills/bills.json",
        "addpay": False,
        "append": "",
        "useSpawn": "false",
        "timer": "",
        "oldrc": False,
        "name": "Atomic 2 - replace bills.json",
        "x": 760,
        "y": 200,
        "wires": [[], [], ["bills_atomic_result"]],
    })

    flows.append({
        "id": "bills_atomic_result",
        "type": "function",
        "z": "bills_flow_group",
        "name": "Atomic save result",
        "func": 'let code = 0;\\n'
                'if (typeof msg.payload === "number") code = msg.payload;\\n'
                'else if (msg.payload && typeof msg.payload.code !== "undefined") code = Number(msg.payload.code);\\n'
                'else if (msg.rc && typeof msg.rc.code !== "undefined") code = Number(msg.rc.code);\\n'
                'if (code === 0) { msg.statusCode = 200; msg.payload = {ok:true}; }\\n'
                'else { msg.statusCode = 500; msg.payload = {ok:false,error:"atomic save failed",code:code}; }\\n'
                'return msg;',
        "outputs": 1,
        "noerr": 0,
        "initialize": "",
        "finalize": "",
        "libs": [],
        "x": 960,
        "y": 200,
        "wires": [["http_resp_post"]],
    })

    print("=== PREPARE HTML ===")
    html = r'''<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>帳單管理系統</title>
<style>
body{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;margin:20px;background:#f5f5f5;color:#222}
.wrap{max-width:1200px;margin:auto}.card{background:#fff;padding:16px;margin-bottom:16px;border-radius:10px}
h1{margin-top:0}input,button{font-size:16px;padding:7px 9px;margin:3px}button{cursor:pointer}
table{width:100%;border-collapse:collapse;background:#fff}th,td{padding:9px;border-bottom:1px solid #ddd;text-align:left}
.money{text-align:right;white-space:nowrap}.actions{white-space:nowrap}.paid{opacity:.6}
#form{display:none}#status{margin-left:10px;font-weight:700}.auth{display:flex;flex-wrap:wrap;align-items:center;gap:4px}
@media(max-width:800px){table{font-size:13px}th,td{padding:5px}}
</style>
</head>
<body>
<div class="wrap">
<div class="card">
<h1>帳單管理系統</h1>
<div class="auth">
<label>帳號</label><input id="user" value="bills" autocomplete="username">
<label>密碼</label><input id="pass" type="password" autocomplete="current-password">
<span id="status"></span>
</div>
</div>

<div class="card">
<button onclick="newBill()">新增帳單</button>
<div id="form">
<hr>
<input id="index" type="hidden" value="-1">
<div><label>名稱</label><input id="name"></div>
<div><label>到期日</label><input id="due" type="date"></div>
<div><label>金額</label><input id="amount" type="number" min="0" step="1"></div>
<div><label>週期（月）</label><input id="period" type="number" min="1" value="1"></div>
<div><label>提前通知（天）</label><input id="notify" type="number" min="0" value="2"></div>
<div><label>付款方式</label><input id="methods" placeholder="信用卡, 現金, 自動扣款"></div>
<button onclick="saveForm()">儲存</button>
<button onclick="hideForm()">取消</button>
</div>
</div>

<div class="card">
<table>
<thead><tr>
<th>名稱</th><th>到期日</th><th>金額</th><th>提前</th><th>付款方式</th>
<th>狀態</th><th>繳費時間</th><th>歷史</th><th>操作</th>
</tr></thead>
<tbody id="rows"></tbody>
</table>
</div>
</div>

<script>
let bills=[];
const API_URL="/local/bills/bills.json";
const SAVE_URL="https://noderedlooaeedr.duckdns.org/bills/save";
const $=function(id){return document.getElementById(id);};

function ts(){
  const d=new Date();
  const p=function(n){return String(n).padStart(2,"0");};
  return d.getFullYear()+"-"+p(d.getMonth()+1)+"-"+p(d.getDate())+" "+p(d.getHours())+":"+p(d.getMinutes())+":"+p(d.getSeconds());
}
function norm(b){
  if(b.amount===undefined||b.amount===null)b.amount=0;
  if(b.paid===undefined)b.paid=false;
  if(!b.paid_at)b.paid_at="";
  if(!Array.isArray(b.history))b.history=[];
  if(!Array.isArray(b.payment_methods))b.payment_methods=[];
  if(!b.last_notified)b.last_notified="";
  return b;
}
function esc(v){
  return String(v==null?"":v).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#039;");
}
function money(v){return "NT$"+Number(v||0).toLocaleString("zh-TW");}
function auth(){
  const u=$("user").value.trim(),p=$("pass").value;
  if(!u||!p)throw new Error("請輸入 bills 帳號與密碼");
  const bytes=new TextEncoder().encode(u+":"+p);
  let s="";
  for(const b of bytes)s+=String.fromCharCode(b);
  return btoa(s);
}
async function writeBills(){
  const r=await fetch(SAVE_URL,{method:"POST",mode:"cors",headers:{"Content-Type":"application/json","Authorization":"Basic "+auth()},body:JSON.stringify(bills)});
  if(r.status===401)throw new Error("帳號或密碼錯誤");
  if(!r.ok)throw new Error("HTTP "+r.status);
}
async function load(){
  try{
    const r=await fetch(API_URL+"?t="+Date.now(),{cache:"no-store"});
    if(!r.ok)throw new Error("HTTP "+r.status);
    const x=await r.json();
    if(!Array.isArray(x))throw new Error("bills.json 不是陣列");
    bills=x.map(norm);
    render();
  }catch(e){$("status").textContent="載入失敗："+e.message;}
}
function render(){
  $("rows").innerHTML="";
  bills.forEach(function(b,i){
    norm(b);
    const tr=document.createElement("tr");
    if(b.paid)tr.className="paid";
    let action=b.paid
      ? '<button onclick="undoPaid('+i+')">改回未繳</button>'
      : '<button onclick="markPaid('+i+')">已繳</button>';
    tr.innerHTML=
      "<td>"+esc(b.name)+"</td>"+
      "<td>"+esc(b.due_day)+"</td>"+
      '<td class="money">'+money(b.amount)+"</td>"+
      "<td>"+Number(b.notify_before||0)+" 天</td>"+
      "<td>"+esc(b.payment_methods.join(" / "))+"</td>"+
      "<td>"+(b.paid?"已繳":"未繳")+"</td>"+
      "<td>"+esc(b.paid_at)+"</td>"+
      '<td>'+b.history.length+' 筆 <button onclick="historyView('+i+')">查看</button></td>'+
      '<td class="actions">'+action+
      '<button onclick="editBill('+i+')">編輯</button>'+
      '<button onclick="removeBill('+i+')">刪除</button></td>';
    $("rows").appendChild(tr);
  });
}
function newBill(){
  $("index").value="-1";$("name").value="";$("due").value="";$("amount").value="";
  $("period").value="1";$("notify").value="2";$("methods").value="";$("form").style.display="block";
}
function editBill(i){
  const b=bills[i];
  $("index").value=String(i);$("name").value=b.name||"";$("due").value=b.due_day||"";
  $("amount").value=b.amount||0;$("period").value=b.period||1;$("notify").value=(b.notify_before==null?2:b.notify_before);
  $("methods").value=(b.payment_methods||[]).join(", ");$("form").style.display="block";
}
function hideForm(){$("form").style.display="none";}
async function persist(okText,rollback){
  try{await writeBills();$("status").textContent=okText;await load();return true;}
  catch(e){bills=JSON.parse(rollback);render();$("status").textContent="寫入失敗："+e.message;return false;}
}
async function saveForm(){
  const idx=Number($("index").value),old=idx>=0?bills[idx]:{};
  const bill=norm(Object.assign({},old,{
    name:$("name").value.trim(),due_day:$("due").value,amount:Number($("amount").value||0),
    period:Math.max(1,Number($("period").value||1)),notify_before:Math.max(0,Number($("notify").value||0)),
    payment_methods:$("methods").value.split(",").map(function(x){return x.trim();}).filter(Boolean)
  }));
  if(!bill.name||!bill.due_day){$("status").textContent="名稱與到期日不能空白";return;}
  const rollback=JSON.stringify(bills);
  if(idx>=0)bills[idx]=bill;else bills.push(bill);
  if(await persist("已儲存",rollback))hideForm();
}
async function markPaid(i){
  const b=bills[i];
  if(!confirm("確認 "+b.name+" 已繳？\\n金額："+money(b.amount)))return;
  const rollback=JSON.stringify(bills);
  b.paid=true;b.paid_at=ts();
  b.history.push({due_day:b.due_day,amount:Number(b.amount||0),paid_at:b.paid_at,payment_methods:[].concat(b.payment_methods||[])});
  await persist(b.name+" 已標記為已繳，提醒停止",rollback);
}
async function undoPaid(i){
  const b=bills[i],rollback=JSON.stringify(bills);
  if(Array.isArray(b.history)&&b.history.length){
    const last=b.history[b.history.length-1];
    if(last.due_day===b.due_day&&last.paid_at===b.paid_at)b.history.pop();
  }
  b.paid=false;b.paid_at="";
  await persist(b.name+" 已改回未繳",rollback);
}
async function removeBill(i){
  if(!confirm("確定刪除 "+bills[i].name+"？"))return;
  const rollback=JSON.stringify(bills);bills.splice(i,1);await persist("已刪除",rollback);
}
function historyView(i){
  const b=bills[i];
  if(!b.history.length){alert(b.name+" 尚無繳費紀錄");return;}
  const text=b.history.map(function(h,n){
    return (n+1)+". "+h.due_day+"  "+money(h.amount)+"\\n繳費："+h.paid_at+"\\n方式："+(h.payment_methods||[]).join(" / ");
  }).join("\\n\\n--------------------\\n\\n");
  alert(b.name+" 歷史紀錄\\n\\n"+text);
}
load();
</script>
</body>
</html>
'''

    print("=== VALIDATE CANDIDATE ===")
    if "bill.paid === true" not in core["func"]:
        raise RuntimeError("paid stop logic missing")
    if "notifyBefore" not in core["func"]:
        raise RuntimeError("notify_before logic missing")
    if "amountText" not in core["func"]:
        raise RuntimeError("amount LINE logic missing")
    if write_node["filename"] != "/storage/docker/share/data/bills/bills.tmp":
        raise RuntimeError("atomic save target wrong")
    if 'id="amount"' not in html or "markPaid" not in html or "Authorization" not in html:
        raise RuntimeError("HTML candidate validation failed")

    print("=== STOP NODE-RED ===")
    stop_nodered()

    print("=== INSTALL ===")
    dump_json_atomic(BILLS, bills, indent=2)
    dump_json_atomic(FLOW, flows, indent=None)

    html_tmp = HTML + ".upgrade.tmp"
    with open(html_tmp, "w", encoding="utf-8") as f:
        f.write(html)
    replace_preserve(html_tmp, HTML)

    print("=== START NODE-RED ===")
    start_nodered()
    time.sleep(2)

    final_flows = load_json(FLOW)
    final_bills = load_json(BILLS)
    final_core = node(final_flows, "e7394ecf2e7dcb7b")
    final_write = node(final_flows, "write_bills_file")
    final_current = node(final_flows, "c4de7e1dc5989247")

    print("paid_stop =", "bill.paid === true" in final_core.get("func", ""))
    print("notify_before =", "notifyBefore" in final_core.get("func", ""))
    print("amount_line =", "amountText" in final_core.get("func", ""))
    print("current_21_enabled =", final_current is not None and not final_current.get("d", False))
    print("atomic_target =", final_write.get("filename"))
    print("db_fields =", all(all(k in b for k in ("amount","paid","paid_at","history")) for b in final_bills))
    print("bill_count =", len(final_bills))

    ps = sh("docker", "ps", "--filter", "name=nodered", "--format", "{{.Status}}", check=False)
    print("nodered =", (ps.stdout or "").strip())

    print("=== DONE ===")
    print("Open: https://halooaeedr.duckdns.org/local/bills/bill_manager.html")

except Exception as e:
    print("ERROR:", e, file=sys.stderr)
    print("=== RESTORE ===", file=sys.stderr)

    for dst, bak in backups.items():
        if os.path.isfile(bak):
            shutil.copy2(bak, dst)

    start_nodered()
    raise
