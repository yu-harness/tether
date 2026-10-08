/* pico 演示站 · run 回放逻辑
 * 数据来自 assets/events.js（由真实 trace.jsonl 原样生成）。
 * 不做静默容错：数据缺失或格式异常直接报错。
 */
"use strict";

if (typeof TRACE_EVENTS === "undefined" || !Array.isArray(TRACE_EVENTS) || TRACE_EVENTS.length === 0) {
  throw new Error("TRACE_EVENTS 未加载或为空：请确认 assets/events.js 存在且由 trace.jsonl 生成。");
}

/* ---------- 数据预处理 ---------- */

var events = TRACE_EVENTS.map(function (ev, i) {
  if (!ev.created_at || !ev.event) {
    throw new Error("第 " + i + " 条事件缺少 created_at 或 event 字段。");
  }
  return ev;
});

var T0 = new Date(events[0].created_at).getTime();
var offsets = events.map(function (ev) {
  return new Date(ev.created_at).getTime() - T0;
});

var finishedEv = events[events.length - 1];
var TOTAL_MS =
  finishedEv.event === "run_finished" && typeof finishedEv.run_duration_ms === "number"
    ? finishedEv.run_duration_ms
    : offsets[offsets.length - 1] + 400;

/* ---------- 工具函数 ---------- */

function esc(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function fmtOffset(ms) {
  return "+" + (ms / 1000).toFixed(3) + "s";
}

function fmtNum(n) {
  return Number(n).toLocaleString("en-US");
}

function shortHash(s) {
  return typeof s === "string" && s.length > 16 ? s.slice(0, 12) + "…" : s;
}

function el(tag, className, html) {
  var node = document.createElement(tag);
  if (className) node.className = className;
  if (html !== undefined) node.innerHTML = html;
  return node;
}

function dlRow(label, value) {
  return "<dt>" + esc(label) + "</dt><dd>" + value + "</dd>";
}

/* ---------- 事件卡片渲染 ---------- */

function badge(text, kind) {
  return '<span class="ev-badge badge-' + kind + '">' + esc(text) + "</span>";
}

function renderBody(ev) {
  var html = "";

  if (ev.event === "run_started") {
    html += "<dl>";
    html += dlRow("task_id", esc(ev.task_id));
    html += dlRow("user_request", esc(ev.user_request));
    html += "</dl>";
  } else if (ev.event === "prompt_built") {
    var m = ev.prompt_metadata;
    if (!m) throw new Error("prompt_built 事件缺少 prompt_metadata。");
    html += "<dl>";
    html += dlRow("prompt 字符", fmtNum(m.prompt_chars) + " / 预算 " + fmtNum(m.prompt_budget_chars));
    html += dlRow("prefix 变化", m.prefix_changed ? "是（重新组装）" : "否（跨轮稳定）");
    html += dlRow("恢复状态", esc(m.resume_status));
    html += dlRow("prefix_hash", esc(shortHash(m.prefix_hash)));
    html += "</dl>";
    html += '<div class="ev-label">各 section 渲染字符 / 预算字符（缩减顺序：' +
      esc(m.reduction_order.join(" → ")) + "）</div>";
    html += '<div class="ev-sections"><table><tr><th>section</th><th>rendered</th><th>budget</th></tr>';
    m.section_order.forEach(function (name) {
      var sec = m.sections[name];
      if (!sec) throw new Error("prompt_metadata.sections 缺少 " + name + " 段。");
      html += "<tr><td>" + esc(name) + "</td><td>" + fmtNum(sec.rendered_chars) +
        "</td><td>" + (sec.budget_chars === null ? "不限" : fmtNum(sec.budget_chars)) + "</td></tr>";
    });
    html += "</table></div>";
  } else if (ev.event === "model_requested") {
    html += "<dl>";
    html += dlRow("第几次调用", esc(ev.attempts));
    html += dlRow("已执行工具步数", esc(ev.tool_steps));
    html += dlRow("prompt_cache_key", esc(shortHash(ev.prompt_cache_key)));
    html += "</dl>";
  } else if (ev.event === "model_parsed") {
    var c = ev.completion_metadata;
    if (!c) throw new Error("model_parsed 事件缺少 completion_metadata。");
    html += "<dl>";
    html += dlRow("输入 token（未命中）", fmtNum(c.input_tokens));
    html += dlRow("缓存命中 token", fmtNum(c.cache_read_tokens) + (c.cache_hit ? "（命中）" : "（未命中）"));
    html += dlRow("输出 token", fmtNum(c.output_tokens));
    html += dlRow("stop_reason", esc(c.stop_reason));
    html += "</dl>";
  } else if (ev.event === "tool_executed") {
    html += "<dl>";
    html += dlRow("风险等级", esc(ev.risk_level));
    if (ev.tool_error_code) html += dlRow("拦截原因", esc(ev.tool_error_code));
    html += dlRow("工作区变更", ev.workspace_changed ? "是" : "否");
    html += "</dl>";
    html += '<div class="ev-label">参数</div><pre>' + esc(JSON.stringify(ev.args, null, 2)) + "</pre>";
    html += '<div class="ev-label">结果</div><pre>' + esc(ev.result) + "</pre>";
  } else if (ev.event === "checkpoint_created") {
    html += "<dl>";
    html += dlRow("checkpoint_id", esc(ev.checkpoint_id));
    html += dlRow("触发方式", esc(ev.trigger));
    html += "</dl>";
  } else if (ev.event === "run_finished") {
    html += "<dl>";
    html += dlRow("run 总耗时", fmtNum(ev.run_duration_ms) + " ms");
    html += dlRow("停止原因", esc(ev.stop_reason));
    html += "</dl>";
    html += '<div class="ev-label">最终回答</div>';
    html += '<div class="ev-final">' + esc(ev.final_answer) + "</div>";
  } else {
    /* runtime_identity_mismatch 等其余事件：全字段平铺 */
    html += "<dl>";
    Object.keys(ev).forEach(function (k) {
      if (k === "created_at" || k === "event" || k === "duration_ms") return;
      var v = typeof ev[k] === "object" ? JSON.stringify(ev[k]) : String(ev[k]);
      html += dlRow(k, esc(v));
    });
    html += "</dl>";
  }
  return html;
}

function headBadge(ev) {
  if (ev.event === "model_parsed") {
    return ev.kind === "tool" ? badge("kind: tool", "info") : badge("kind: final", "ok");
  }
  if (ev.event === "tool_executed") {
    return ev.tool_status === "ok" ? badge("ok", "ok") : badge(ev.tool_status, "err");
  }
  if (ev.event === "run_finished") {
    return ev.status === "completed" ? badge(ev.status, "ok") : badge(ev.status, "err");
  }
  return "";
}

function renderCard(ev, index) {
  var rejected = ev.event === "tool_executed" && ev.tool_status !== "ok";
  var card = el(
    "article",
    "ev-card ev-" + ev.event + (rejected ? " ev-rejected" : "")
  );
  var head = el("div", "ev-head");
  head.innerHTML =
    '<span class="ev-index">#' + (index + 1) + "</span>" +
    '<span class="ev-name">' + esc(ev.event) + "</span>" +
    '<span class="ev-time">' + fmtOffset(offsets[index]) + "</span>" +
    (typeof ev.duration_ms === "number"
      ? '<span class="ev-dur">' + fmtNum(ev.duration_ms) + " ms</span>"
      : "") +
    headBadge(ev);
  var body = el("div", "ev-body", renderBody(ev));
  card.appendChild(head);
  card.appendChild(body);
  return card;
}

/* ---------- 摘要条（全部从事件数据计算，非硬编码） ---------- */

function renderSummary() {
  var tools = events.filter(function (ev) { return ev.event === "tool_executed"; });
  var parsed = events.filter(function (ev) { return ev.event === "model_parsed"; });
  var modelCalls = events.filter(function (ev) { return ev.event === "model_requested"; }).length;

  var cacheRead = 0;
  var inputMiss = 0;
  parsed.forEach(function (ev) {
    cacheRead += ev.completion_metadata.cache_read_tokens;
    inputMiss += ev.completion_metadata.input_tokens;
  });
  var hitRate = (cacheRead / (cacheRead + inputMiss)) * 100;

  var toolSeq = tools
    .map(function (ev) { return ev.name + (ev.tool_status === "ok" ? "" : "(" + ev.tool_status + ")"); })
    .join(" → ");

  var box = document.getElementById("replay-summary");
  box.appendChild(el("span", "summary-chip", "工具序列：<strong>" + esc(toolSeq) + "</strong>"));
  box.appendChild(el("span", "summary-chip", "模型调用：<strong>" + modelCalls + " 次</strong>"));
  box.appendChild(el("span", "summary-chip", "prefix 缓存命中率（本 run）：<strong>" + hitRate.toFixed(1) + "%</strong>"));
  box.appendChild(el("span", "summary-chip chip-ok", "最终状态：<strong>" + esc(finishedEv.status) + "</strong>"));
  box.appendChild(el("span", "summary-chip", "run 时长：<strong>" + fmtNum(finishedEv.run_duration_ms) + " ms</strong>"));
}

/* ---------- 播放器 ---------- */

var timelineEl = document.getElementById("timeline");
var progressEl = document.getElementById("player-progress");
var thumbEl = document.getElementById("player-thumb");
var counterEl = document.getElementById("player-counter");
var timeCurEl = document.getElementById("time-current");
var timeTotalEl = document.getElementById("time-total");
var btnPlay = document.getElementById("btn-play");
var btnStep = document.getElementById("btn-step");
var btnReset = document.getElementById("btn-reset");
var trackEl = document.getElementById("player-track");

var playhead = 0;        /* 当前播放位置（ms） */
var shownCount = 0;      /* 已上屏的事件数 */
var playing = false;
var rafId = null;
var lastFrameTs = null;

function appendDueCards() {
  var appended = false;
  while (shownCount < events.length && offsets[shownCount] <= playhead) {
    var card = renderCard(events[shownCount], shownCount);
    timelineEl.appendChild(card);
    shownCount += 1;
    appended = true;
  }
  if (appended && playing) {
    var last = timelineEl.lastElementChild;
    if (last) last.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
}

function updateChrome() {
  var pct = TOTAL_MS === 0 ? 100 : Math.min(100, (playhead / TOTAL_MS) * 100);
  progressEl.style.width = pct + "%";
  thumbEl.style.left = pct + "%";
  counterEl.textContent = shownCount + " / " + events.length;
  timeCurEl.textContent = fmtOffset(playhead);
}

function setPlayhead(ms, rebuild) {
  playhead = Math.max(0, Math.min(TOTAL_MS, ms));
  if (rebuild) {
    timelineEl.innerHTML = "";
    shownCount = 0;
  }
  appendDueCards();
  updateChrome();
}

function stopAtEnd() {
  playing = false;
  btnPlay.textContent = "播放";
  if (rafId !== null) {
    cancelAnimationFrame(rafId);
    rafId = null;
  }
}

function frame(ts) {
  if (!playing) return;
  if (lastFrameTs !== null) {
    playhead = Math.min(TOTAL_MS, playhead + (ts - lastFrameTs));
  }
  lastFrameTs = ts;
  appendDueCards();
  updateChrome();
  if (playhead >= TOTAL_MS && shownCount >= events.length) {
    stopAtEnd();
    return;
  }
  rafId = requestAnimationFrame(frame);
}

btnPlay.addEventListener("click", function () {
  if (playing) {
    stopAtEnd();
    return;
  }
  if (playhead >= TOTAL_MS) {
    setPlayhead(0, true); /* 播完后再次播放从头开始 */
  }
  playing = true;
  btnPlay.textContent = "暂停";
  lastFrameTs = null;
  rafId = requestAnimationFrame(frame);
});

btnStep.addEventListener("click", function () {
  stopAtEnd();
  if (shownCount >= events.length) return;
  /* 推进到下一条事件的时刻（+1ms 保证 <= 判定生效） */
  setPlayhead(offsets[shownCount] + 1, false);
});

btnReset.addEventListener("click", function () {
  stopAtEnd();
  setPlayhead(0, true);
});

trackEl.addEventListener("click", function (e) {
  var rect = trackEl.getBoundingClientRect();
  var ratio = (e.clientX - rect.left) / rect.width;
  var target = ratio * TOTAL_MS;
  stopAtEnd();
  setPlayhead(target, target < playhead);
});

/* ---------- 初始化 ---------- */

timeTotalEl.textContent = fmtOffset(TOTAL_MS);
renderSummary();
setPlayhead(0, true);
console.log("pico replay: 已加载 " + events.length + " 条事件，run 时长 " + TOTAL_MS + " ms。");
