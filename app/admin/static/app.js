// Общие утилиты веб-панели. Токен передаётся через httponly-cookie,
// но fetch к /api/* требует заголовок Authorization -> читаем токен из cookie нельзя (httponly).
// Поэтому API-роуты панели читают токен и из cookie тоже (deps.get_admin_from_cookie не используется),
// здесь используем credentials:'include' и дублирующий заголовок из meta, если задан.

async function api(path, options = {}) {
  const opts = Object.assign({ credentials: "include", headers: {} }, options);
  // Токен доступен серверу через cookie; для API также пробуем localStorage (fallback).
  const t = localStorage.getItem("access_token");
  if (t) opts.headers["Authorization"] = "Bearer " + t;
  opts.headers["Content-Type"] = opts.headers["Content-Type"] || "application/json";
  const res = await fetch(path, opts);
  if (res.status === 401) { window.location = "/admin/login"; return null; }
  if (!res.ok) throw new Error("HTTP " + res.status);
  const ct = res.headers.get("content-type") || "";
  return ct.includes("application/json") ? res.json() : res;
}

function esc(s) {
  if (s === null || s === undefined) return "";
  return String(s).replace(/[&<>"']/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }[c]));
}

function badge(status) {
  const map = { present:"present", late:"late", absent:"absent", completed:"completed", on_leave:"present", sick:"absent" };
  const label = {
    present:"келди", late:"кечикди", absent:"келмади",
    completed:"якунланди", on_leave:"таътилда", sick:"касал"
  };
  return `<span class="badge ${map[status]||''}">${esc(label[status]||status)}</span>`;
}

function fmtTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
}
function fmtMin(min) {
  const h = Math.floor((min||0)/60), m = (min||0)%60;
  return `${h}:${String(m).padStart(2,"0")}`;
}
