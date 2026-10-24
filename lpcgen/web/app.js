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
        cs.innerHTML = sl.colors.map(x => `<option ${colorOf(c, sl.key) === x ? "selected" : ""}>${x}</option>`).join("");
        const sw = document.createElement("span"); sw.className = "sw"; sw.style.background = sl.preview[cs.value] || "#888";
        cs.onchange = () => { setColor(c, it, sl.key, cs.value); sw.style.background = sl.preview[cs.value] || "#888"; refresh(); };
        sub.append(sw, cs);
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
      $("warn").textContent = r.warnings.join(" · ");
    } catch (e) { $("warn").textContent = e.message; }
    if (tok === S.tok) $("busy").classList.add("hidden");
  }, 200);
}

function tick(now) {
  const cv = $("cv"), ctx = cv.getContext("2d");
  const z = +$("zoom").value;
  if (cv.width !== 64 * z) { cv.width = cv.height = 64 * z; }
  ctx.clearRect(0, 0, cv.width, cv.height);
  if (S.img) {
    const a = S.st.anims.find(x => x.id === $("anim").value);
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

$("btnDownload").onclick = async () => {
  $("btnDownload").disabled = true;
  try {
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
  $("setinfo").innerHTML = `<p>Pasta do app: <code>${s.home}</code></p><p>Sprites salvos em: <code>${s.output_dir}</code></p>` +
    s.items.map(i => `<p>• ${i.label}: ${(i.bytes/1048576).toFixed(0)} MB</p>`).join("");
  $("dlgSettings").showModal();
};
$("btnCloseSet").onclick = () => $("dlgSettings").close();
$("btnUninstall").onclick = async () => {
  if (!confirm("Remover a arte baixada e as configurações? Seus sprites gerados não serão apagados.")) return;
  const r = await api("/api/uninstall", {});
  $("setmsg").textContent = "Removido: " + (r.removed.join(", ") || "nada") + (r.failed.length ? " · Falhou: " + r.failed.join("; ") : "") + ". Pode fechar o app.";
};
init().catch(e => { document.body.insertAdjacentHTML("beforeend", `<p class="card">Erro: ${e.message}</p>`); });
