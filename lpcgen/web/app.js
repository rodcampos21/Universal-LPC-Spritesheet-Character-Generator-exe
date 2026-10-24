"use strict";
const $ = (id) => document.getElementById(id);
const TYPE_PT = {body:"Corpo/pele",head:"Cabeça",eyes:"Olho ciclope",facial_eyes:"Olhos",eyebrows:"Sobrancelhas",nose:"Nariz",ears:"Orelhas",
  hair:"Cabelo",beard:"Barba",mustache:"Bigode",clothes:"Camisa",legs:"Calça/saia",shoes:"Sapatos",jacket:"Jaqueta",vest:"Colete",belt:"Cinto",
  hat:"Chapéu",cape:"Capa",backpack:"Mochila",necklace:"Colar",earrings:"Brincos",weapon:"Arma",shield:"Escudo",armour:"Armadura",dress:"Vestido",
  socks:"Meias",apron:"Avental",wings:"Asas",tail:"Cauda",sash:"Faixa",shoulders:"Ombreiras",wrists:"Pulseiras",expression:"Expressão"};
const GROUP_PT = {body:"Corpo",head:"Cabeça",hair:"Cabelo e barba",torso:"Tronco",legs:"Pernas",feet:"Pés",headwear:"Chapéus e acessórios",
  weapons:"Armas e escudos",arms:"Braços",backpack:"Mochilas",beards:"Barbas",tools:"Ferramentas"};
const ORDER = ["body","head","eyes","facial_eyes","eyebrows","nose","ears","hair","beard","mustache","clothes","legs","shoes","jacket","vest","belt","hat","cape","backpack","weapon","shield"];
const S = {body:"male", sel:{}, shared:{}, items:[], st:null, img:null, anims:[], t0:0, tok:0, timer:null};

async function api(path, body) {
  const opt = body === undefined ? {} : {method:"POST", headers:{"X-App":"1","Content-Type":"application/json"}, body:JSON.stringify(body)};
  const r = await fetch(path, opt);
  const j = await r.json();
  if (!r.ok || j.error) throw new Error(j.error || "Erro");
  return j;
}
const label = (t) => TYPE_PT[t] || t.replace(/_/g, " ");

async function init() {
  S.st = await api("/api/status");
  $("outdir").value = S.st.output_dir;
  $("body").innerHTML = S.st.bodies.map(b => `<option value="${b.id}">${b.name}</option>`).join("");
  $("anim").innerHTML = S.st.anims.map(a => `<option value="${a.id}">${a.name}</option>`).join("");
  $("anim").value = "walk";
  $("dir").innerHTML = Object.entries(S.st.dirs).map(([k,v]) => `<option value="${k}">${v}</option>`).join("");
  $("dir").value = "down";
  setInterval(() => api("/api/ping", {}).catch(()=>{}), 5000);
  $("artdir").value = S.st.art_dir; $("outdir0").value = S.st.output_dir;
  if (!S.st.art) { $("setup").classList.remove("hidden"); return; }
  $("setup").classList.add("hidden"); $("app").classList.remove("hidden");
  await loadBody("male", true);
  requestAnimationFrame(tick);
}

async function loadBody(body, fresh) {
  S.body = body; $("body").value = body;
  S.items = (await api("/api/catalog?body=" + body)).items;
  const ids = new Set(S.items.map(i => i.id));
  const keep = {};
  if (!fresh) for (const [k, v] of Object.entries(S.sel)) if (ids.has(v.itemId)) keep[k] = v;
  if (fresh || !keep.body || !keep.head) {
    const d = await api("/api/default", {body});
    for (const k of ["body", "head", "expression", ...(fresh ? Object.keys(d.selections) : [])]) if (!keep[k] && d.selections[k]) keep[k] = d.selections[k];
    S.shared = fresh ? (d.shared || {}) : Object.assign({}, d.shared || {}, S.shared);
  }
  S.sel = keep;
  buildPicker(); refresh();
}

function typesOf() {
  const m = new Map();
  for (const it of S.items) { if (!m.has(it.type)) m.set(it.type, {type: it.type, group: it.group, items: []}); m.get(it.type).items.push(it); }
  return [...m.values()].sort((a,b) => {
    const ia = ORDER.indexOf(a.type), ib = ORDER.indexOf(b.type);
    return (ia<0?99:ia) - (ib<0?99:ib) || a.group.localeCompare(b.group) || a.type.localeCompare(b.type);
  });
}

function buildPicker() {
  const q = $("filter").value.trim().toLowerCase();
  const byGroup = new Map();
  for (const t of typesOf()) {
    if (q && !label(t.type).toLowerCase().includes(q) && !t.items.some(i => i.name.toLowerCase().includes(q))) continue;
    if (!byGroup.has(t.group)) byGroup.set(t.group, []);
    byGroup.get(t.group).push(t);
  }
  const box = $("groups"); box.innerHTML = "";
  for (const [g, types] of byGroup) {
    const d = document.createElement("details");
    d.open = !!q || ["body","head","hair","torso","legs","feet"].includes(g);
    d.innerHTML = `<summary>${GROUP_PT[g] || g}</summary>`;
    for (const t of types) d.appendChild(slotRow(t, q));
    box.appendChild(d);
  }
}

function slotRow(t, q) {
  const wrap = document.createElement("div"); wrap.className = "slot";
  const cur = S.sel[t.type];
  const items = q ? t.items.filter(i => i.name.toLowerCase().includes(q) || label(t.type).toLowerCase().includes(q)) : t.items;
  const subs = [...new Set(items.map(i => i.sub))];
  let opts = `<option value="">— nenhum —</option>`;
  if (t.type === "body") opts = "";
  for (const s of subs) {
    const inner = items.filter(i => i.sub === s).map(i => `<option value="${i.id}" ${cur && cur.itemId === i.id ? "selected" : ""}>${i.name}</option>`).join("");
    opts += subs.length > 1 ? `<optgroup label="${s.split("/").slice(1).join(" / ") || s}">${inner}</optgroup>` : inner;
  }
  wrap.innerHTML = `<span class="lab">${label(t.type)}</span><select>${opts}</select><span class="sub"></span>`;
  const sel = wrap.querySelector("select"), sub = wrap.querySelector(".sub");
  const fill = () => {
    sub.innerHTML = "";
    const c = S.sel[t.type]; if (!c) return;
    const it = S.items.find(i => i.id === c.itemId); if (!it) return;
    if (it.variants.length > 1) {
      const v = document.createElement("select");
      v.innerHTML = it.variants.map(x => `<option ${c.variant === x ? "selected" : ""}>${x}</option>`).join("");
      v.onchange = () => { c.variant = v.value; refresh(); };
      sub.appendChild(v);
    }
    const own = it.slots.filter(sl => !sl.shared);
    if (own.length && !(it.match_body && t.type !== "body" && own.every(sl => sl.material === "body"))) {
      own.forEach(sl => {
        if (it.match_body && t.type !== "body" && sl.material === "body") return;
        const cs = document.createElement("select");
        cs.title = sl.label;
        const curc = colorOf(c, sl.key);
        cs.innerHTML = (curc.startsWith("#") ? `<option selected>${curc}</option>` : "") +
          sl.colors.map(x => `<option ${curc === x ? "selected" : ""}>${x}</option>`).join("");
        const swc = (v) => v.startsWith("#") ? v : (sl.preview[v] || "#888");
        const sw = document.createElement("span"); sw.className = "sw"; sw.style.background = swc(cs.value);
        cs.onchange = () => { setColor(c, it, sl.key, cs.value); sw.style.background = swc(cs.value); refresh(); };
        const pick = document.createElement("input"); pick.type = "color"; pick.title = "Cor livre";
        pick.value = curc.startsWith("#") && curc.length === 7 ? curc : "#888888";
        pick.onchange = () => { setColor(c, it, sl.key, pick.value); buildPicker(); refresh(); };
        sub.append(sw, cs, pick);
      });
    } else if (it.match_body && t.type !== "body" && !own.length) {
      sub.innerHTML = `<span class="muted">cor da pele</span>`;
    }
  };
  sel.onchange = () => {
    if (!sel.value) delete S.sel[t.type]; else S.sel[t.type] = newSel(S.items.find(i => i.id === sel.value), S.sel.body);
    fill(); refresh();
  };
  fill();
  return wrap;
}
function colorOf(c, key) { return typeof c.recolor === "string" ? (key === "color_1" ? c.recolor : "") : (c.recolor || {})[key] || ""; }
function setColor(c, it, key, val) {
  if (it.slots.length === 1) c.recolor = val; else { c.recolor = (typeof c.recolor === "object" && c.recolor) || {}; c.recolor[key] = val; }
}
function newSel(it, bodySel) {
  const s = {itemId: it.id, name: it.name, variant: it.variants[0] || ""};
  if (it.slots.length) {
    s.variant = "";
    const rc = {}; it.slots.forEach(sl => rc[sl.key] = sl.colors[0]);
    s.recolor = it.slots.length === 1 ? rc.color_1 : rc;
  }
  return s;
}

function character() { return {version: 2, bodyType: S.body, selections: S.sel, shared: S.shared}; }

function renderShared() {
  const m = new Map();
  for (const sel of Object.values(S.sel)) {
    const it = S.items.find(i => i.id === sel.itemId); if (!it) continue;
    for (const sl of it.slots) if (sl.shared && !m.has(sl.shared)) m.set(sl.shared, sl);
  }
  const box = $("shared"); box.innerHTML = "";
  if (!m.size) return;
  box.innerHTML = `<summary>Cores compartilhadas</summary>`;
  for (const [k, sl] of m) {
    if (!S.shared[k]) S.shared[k] = sl.colors[0];
    const w = document.createElement("div"); w.className = "slot";
    w.innerHTML = `<span class="lab">${k === "eyes" ? "Cor dos olhos" : sl.label}</span><span></span><span class="sub"><span class="sw"></span><select>${sl.colors.map(c => `<option ${S.shared[k] === c ? "selected" : ""}>${c}</option>`).join("")}</select></span>`;
    const sw = w.querySelector(".sw"), cs = w.querySelector("select");
    sw.style.background = sl.preview[cs.value] || "#888";
    cs.onchange = () => { S.shared[k] = cs.value; sw.style.background = sl.preview[cs.value] || "#888"; refresh(true); };
    box.appendChild(w);
  }
}

function refresh(keepShared) {
  if (keepShared !== true) renderShared();
  clearTimeout(S.timer);
  S.timer = setTimeout(async () => {
    const tok = ++S.tok; $("busy").classList.remove("hidden");
    try {
      const r = await api("/api/preview", {character: character()});
      if (tok !== S.tok) return;
      const img = new Image();
      img.onload = () => { S.img = img; S.t0 = performance.now(); };
      img.src = r.png;
      S.custom = {};
      for (const [k, v] of Object.entries(r.custom || {})) { const ci = new Image(); ci.src = v.png; S.custom[k] = {img: ci, fs: v.frameSize, cols: v.cols}; }
      const cur = $("anim").value;
      $("anim").innerHTML = S.st.anims.map(a => `<option value="${a.id}">${a.name}</option>`).join("") +
        Object.keys(S.custom).map(k => `<option value="x:${k}">Extra: ${k}</option>`).join("");
      $("anim").value = [...$("anim").options].some(o => o.value === cur) ? cur : "walk";
      $("warn").textContent = r.warnings.join(" · ");
    } catch (e) { $("warn").textContent = e.message; }
    if (tok === S.tok) $("busy").classList.add("hidden");
  }, 200);
}

function tick(now) {
  const cv = $("cv"), ctx = cv.getContext("2d");
  let z = +$("zoom").value;
  const av = $("anim").value;
  const cu = av.startsWith("x:") ? S.custom && S.custom[av.slice(2)] : null;
  const fsz = cu ? cu.fs : 64;
  if (cu && fsz > 64) z = Math.max(1, z - 1);
  if (cv.width !== fsz * z) { cv.width = cv.height = fsz * z; }
  ctx.clearRect(0, 0, cv.width, cv.height);
  if (cu && cu.img.complete) {
    const di = ["up","left","down","right"].indexOf($("dir").value);
    const idx = Math.floor((now - S.t0) / 1000 * 10) % cu.cols;
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(cu.img, idx * fsz, di * fsz, fsz, fsz, 0, 0, fsz * z, fsz * z);
  } else if (S.img && !cu) {
    const a = S.st.anims.find(x => x.id === av);
    const di = ["up","left","down","right"].indexOf($("dir").value);
    const row = a.row + (a.rows === 4 ? di : 0);
    const idx = a.cycle[Math.floor((now - S.t0) / 1000 * a.fps) % a.cycle.length];
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(S.img, idx * 64, row * 64, 64, 64, 0, 0, 64 * z, 64 * z);
  }
  requestAnimationFrame(tick);
}

async function pollJob(id, bar, msg, done) {
  bar.classList.remove("hidden");
  for (;;) {
    const j = await api("/api/jobs/" + id);
    bar.firstElementChild.style.width = (j.progress * 100) + "%";
    msg.textContent = j.message;
    if (j.status === "done") { done(j.result); break; }
    if (j.status === "error") { msg.textContent = "Erro: " + j.error; break; }
    if (j.status === "cancelled") break;
    await new Promise(r => setTimeout(r, 700));
  }
}

async function pickInto(inputId, title) {
  const r = await api("/api/pickfolder", {initial: $(inputId).value, title});
  if (r.path) $(inputId).value = r.path;
  return r.path;
}
$("btnPickArt").onclick = () => pickInto("artdir", "Onde guardar a arte do LPC?").catch(e => $("dlmsg").textContent = e.message);
$("btnPickOut0").onclick = () => pickInto("outdir0", "Onde salvar os sprites?").catch(e => $("dlmsg").textContent = e.message);
$("btnDownload").onclick = async () => {
  $("btnDownload").disabled = true;
  try {
    const a = await api("/api/artdir", {path: $("artdir").value, move: false});
    $("artdir").value = a.art_dir;
    await api("/api/config", {output_dir: $("outdir0").value});
    const r = await api("/api/download", {});
    if (r.job) await pollJob(r.job, $("dlbar"), $("dlmsg"), () => {});
    S.st = await api("/api/status");
    if (S.st.art) { location.reload(); } else $("btnDownload").disabled = false;
  } catch (e) { $("dlmsg").textContent = e.message; $("btnDownload").disabled = false; }
};
$("body").onchange = () => loadBody($("body").value, false);
$("filter").oninput = buildPicker;
$("btnRandom").onclick = async () => {
  const r = await api("/api/random", {body: S.body});
  S.sel = r.selections; S.shared = r.shared || {}; await loadBody(S.body, false);
};
$("btnReset").onclick = () => loadBody(S.body, true);
$("btnPick").onclick = async () => {
  try {
    const r = await api("/api/pickfolder", {initial: $("outdir").value});
    if (r.path) { $("outdir").value = r.path; await saveDir(); }
  } catch (e) { $("savemsg").textContent = e.message; }
};
async function saveDir() {
  try { const r = await api("/api/config", {output_dir: $("outdir").value}); $("outdir").value = r.output_dir; return true; }
  catch (e) { $("savemsg").textContent = e.message; return false; }
}
$("outdir").onchange = saveDir;
$("btnOpen").onclick = () => api("/api/openfolder", {path: $("outdir").value}).catch(e => $("savemsg").textContent = e.message);
const opts = () => ({per_anim: $("oAnim").checked, gifs: $("oGif").checked, godot: $("oGodot").checked});
$("btnSave").onclick = async () => {
  $("savemsg").textContent = "Salvando…";
  if (!(await saveDir())) return;
  try {
    const r = await api("/api/save", {character: character(), name: $("name").value, options: opts(), output_dir: $("outdir").value});
    $("savemsg").textContent = "Salvo em: " + r.folder;
  } catch (e) { $("savemsg").textContent = "Erro: " + e.message; }
};
$("btnBatch").onclick = async () => {
  if (!(await saveDir())) return;
  $("bmsg").textContent = "";
  try {
    const r = await api("/api/batch", {count: +$("bcount").value, prefix: $("bprefix").value, output_dir: $("outdir").value, ...opts()});
    await pollJob(r.job, $("bbar"), $("bmsg"), (res) => { $("bmsg").textContent = `${res.count} personagens salvos em: ${res.folder}`; });
  } catch (e) { $("bmsg").textContent = "Erro: " + e.message; }
};
function showReport(r) {
  $("areport").innerHTML = `<p>Salvo em: ${r.folder}</p><table><tr><th>Animação</th><th>Quadros</th><th>Original</th><th>Caixa</th><th>Economia</th></tr>` +
    r.report.map(x => `<tr><td>${x.anim}</td><td>${x.dirs}×${x.frames}</td><td>${x.original}px</td><td>${x.cell[0]}×${x.cell[1]}</td><td>${x.saved_pct}%</td></tr>`).join("") + "</table>";
}
const aopts = () => ({mode: $("amode").value, loose: $("aloose").checked, output_dir: $("outdir").value});
$("btnAnalyze").onclick = async () => {
  $("areport").textContent = "Analisando…";
  if (!(await saveDir())) return;
  try { showReport(await api("/api/analyze", {character: character(), name: $("name").value, ...aopts()})); }
  catch (e) { $("areport").textContent = "Erro: " + e.message; }
};
$("btnAnalyzeDir").onclick = async () => {
  try {
    const r = await api("/api/pickfolder", {initial: $("outdir").value, title: "Pasta com os PNG para analisar"});
    if (!r.path) return;
    $("areport").textContent = "Analisando a pasta…";
    if (!(await saveDir())) return;
    const res = await api("/api/analyze_dir", {dir: r.path, ...aopts(), frame_size: +$("afs").value});
    $("areport").innerHTML = `<p>${res.results.length} arquivo(s) analisado(s) em: ${res.folder}</p>` +
      (res.errors.length ? `<p class="warn">${res.errors.join("<br>")}</p>` : "");
  } catch (e) { $("areport").textContent = "Erro: " + e.message; }
};
$("btnAnalyzePng").onclick = () => $("filePng").click();
$("filePng").onchange = async () => {
  const f = $("filePng").files[0]; if (!f) return;
  $("areport").textContent = "Analisando…";
  try {
    const b64 = await new Promise((res, rej) => { const fr = new FileReader(); fr.onload = () => res(fr.result); fr.onerror = rej; fr.readAsDataURL(f); });
    if (!(await saveDir())) return;
    showReport(await api("/api/analyze_png", {png: b64, frame_size: +$("afs").value, name: f.name.replace(/\.png$/i, ""), ...aopts()}));
  } catch (e) { $("areport").textContent = "Erro: " + e.message; }
  $("filePng").value = "";
};
// --- Skin a partir de imagem (experimental) ---
const SKIN_ROWS = [["skin","Pele",["body"],false],["hair","Cabelo",["hair","beard","mustache"],false],
  ["shirt","Camisa",["clothes"],true],["pants","Calça",["legs"],true],["shoes","Sapatos",["shoes"],false]];
const PATTERNS = [["","Cor lisa"],["stripes","Listras horizontais"],["vstripes","Listras verticais"],["diagonal","Diagonal"],
  ["checker","Xadrez"],["dots","Bolinhas"],["camo","Camuflagem"]];
$("btnSkin").onclick = () => $("fileSkin").click();
$("fileSkin").onchange = async () => {
  const f = $("fileSkin").files[0]; if (!f) return;
  try {
    const b64 = await new Promise((res, rej) => { const fr = new FileReader(); fr.onload = () => res(fr.result); fr.onerror = rej; fr.readAsDataURL(f); });
    $("skinThumb").src = b64; $("skinThumb").classList.remove("hidden");
    const r = await api("/api/skin/colors", {png: b64});
    $("skinRows").innerHTML = SKIN_ROWS.map(([k, lab, , pat]) => `<div class="slot"><span class="lab">${lab}</span>
      <span class="sub"><input type="color" id="sk_${k}" value="${r.suggest[k]}">${pat ? `<select id="skp_${k}">${PATTERNS.map(p => `<option value="${p[0]}">${p[1]}</option>`).join("")}</select>
      <input type="color" id="sk2_${k}" value="${r.secondary[k]}" title="Segunda cor da estampa">` : ""}</span><span></span></div>`).join("") +
      `<p class="muted">Cores da imagem: ${r.palette.map(p => `<span class="sw" title="${p.hex} (${p.pct}%)" style="background:${p.hex}"></span>`).join(" ")}</p>`;
    $("skinBox").classList.remove("hidden"); $("skinMsg").textContent = "";
  } catch (e) { $("skinMsg").textContent = e.message; $("skinBox").classList.remove("hidden"); }
  $("fileSkin").value = "";
};
$("btnSkinApply").onclick = () => {
  const missing = [];
  for (const [k, lab, types, pat] of SKIN_ROWS) {
    let hit = false;
    for (const t of types) {
      const c = S.sel[t]; if (!c) continue;
      const it = S.items.find(i => i.id === c.itemId); if (!it || !it.slots.length) continue;
      hit = true;
      const own = it.slots.find(sl => !sl.shared && !(it.match_body && t !== "body" && sl.material === "body"));
      if (!own) continue;
      const hex = $("sk_" + k).value;
      if (it.slots.length === 1) c.recolor = hex; else { c.recolor = (typeof c.recolor === "object" && c.recolor) || {}; c.recolor[own.key] = hex; }
      c.variant = "";
      if (pat && $("skp_" + k).value) c.pattern = {kind: $("skp_" + k).value, color2: $("sk2_" + k).value, scale: 3}; else delete c.pattern;
    }
    if (!hit) missing.push(lab);
  }
  $("skinMsg").textContent = missing.length ? "Sem peça para: " + missing.join(", ") + " (escolha uma peça e aplique de novo)." : "Cores aplicadas. Confira na prévia.";
  buildPicker(); refresh();
};
$("btnLoad").onclick = () => $("fileJson").click();
$("fileJson").onchange = async () => {
  const f = $("fileJson").files[0]; if (!f) return;
  try {
    const d = JSON.parse(await f.text());
    if (!d.selections) throw new Error("Esse arquivo não parece um personagem.");
    S.sel = d.selections; S.shared = d.shared || {};
    await loadBody(d.bodyType || "male", false);
  } catch (e) { $("savemsg").textContent = e.message; }
  $("fileJson").value = "";
};
$("anim").onchange = () => { S.t0 = performance.now(); };
$("btnSettings").onclick = async () => {
  const s = await api("/api/settings");
  $("artdir2").value = s.art_dir; $("outdir2").value = s.output_dir; $("setmsg2").textContent = "";
  $("setinfo").innerHTML = `<p>Pasta do app: <code>${s.home}</code></p><p>Sprites salvos em: <code>${s.output_dir}</code></p>` +
    s.items.map(i => `<p>• ${i.label}: ${(i.bytes/1048576).toFixed(0)} MB</p>`).join("");
  $("dlgSettings").showModal();
};
$("btnPickArt2").onclick = async () => {
  try {
    const p = await pickInto("artdir2", "Para onde mover a arte do LPC?"); if (!p) return;
    $("setmsg2").textContent = "Mudando…";
    const r = await api("/api/artdir", {path: p, move: true});
    if (r.job) await pollJob(r.job, $("bbar"), $("setmsg2"), () => {});
    $("artdir2").value = r.art_dir; $("setmsg2").textContent = "Arte em: " + r.art_dir;
    S.st = await api("/api/status");
  } catch (e) { $("setmsg2").textContent = e.message; }
};
$("btnPickOut2").onclick = async () => {
  try {
    const p = await pickInto("outdir2", "Onde salvar os sprites?"); if (!p) return;
    const r = await api("/api/config", {output_dir: p});
    $("outdir2").value = r.output_dir; $("outdir").value = r.output_dir; $("setmsg2").textContent = "Sprites serão salvos em: " + r.output_dir;
  } catch (e) { $("setmsg2").textContent = e.message; }
};
$("btnCloseSet").onclick = () => $("dlgSettings").close();
$("btnUninstall").onclick = async () => {
  if (!confirm("Remover a arte baixada e as configurações? Seus sprites gerados não serão apagados.")) return;
  const r = await api("/api/uninstall", {});
  $("setmsg").textContent = "Removido: " + (r.removed.join(", ") || "nada") + (r.failed.length ? " · Falhou: " + r.failed.join("; ") : "") + ". Pode fechar o app.";
};
init().catch(e => { document.body.insertAdjacentHTML("beforeend", `<p class="card">Erro: ${e.message}</p>`); });
