function appUrl(path = "") {
  const pathname = window.location.pathname;
  const toolsMarker = "/tools/";
  const toolsIndex = pathname.lastIndexOf(toolsMarker);
  let basePath;
  if (toolsIndex >= 0) {
    basePath = pathname.slice(0, toolsIndex + 1);
  } else {
    basePath = pathname.endsWith("/") ? pathname : `${pathname}/`;
  }
  return `${basePath}${path.replace(/^\/+/, "")}`;
}

document.querySelectorAll("[data-app-path]").forEach((link) => {
  link.setAttribute("href", appUrl(link.dataset.appPath));
});

function formatBytes(bytes) {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / (1024 ** index)).toFixed(index === 0 ? 0 : 2)} ${units[index]}`;
}

function setStatus(element, message, kind = "info") {
  element.textContent = message;
  element.className = `status ${kind}`;
}

function clearStatus(element) {
  element.className = "status hidden";
  element.textContent = "";
}

function renderErrors(container, errors) {
  container.replaceChildren();
  if (!errors || errors.length === 0) return;
  const box = document.createElement("div");
  box.className = "error-box";
  const title = document.createElement("strong");
  title.textContent = `${errors.length} 个项目处理失败或被跳过`;
  box.append(title);
  const list = document.createElement("ul");
  errors.forEach((message) => {
    const item = document.createElement("li");
    item.textContent = message;
    list.append(item);
  });
  box.append(list);
  container.append(box);
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || `请求失败 (${response.status})`);
  return payload;
}
