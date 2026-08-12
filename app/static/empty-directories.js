const emptyForm = document.querySelector("#scan-form");
const emptyStatus = document.querySelector("#status");
const emptyResults = document.querySelector("#results");
const directoryList = document.querySelector("#directory-list");
const emptySummary = document.querySelector("#result-summary");
const emptyErrors = document.querySelector("#error-list");
const emptyDeleteButton = document.querySelector("#delete-button");
let emptyScanToken = null;

emptyForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  emptyResults.classList.add("hidden");
  emptyDeleteButton.classList.add("hidden");
  emptyScanToken = null;
  setStatus(emptyStatus, "正在扫描目录…");
  const submit = emptyForm.querySelector("button[type=submit]");
  submit.disabled = true;
  try {
    const data = await postJson(appUrl("api/empty-directories/scan"), {
      path: document.querySelector("#path").value,
    });
    emptyScanToken = data.scan_token;
    directoryList.replaceChildren();
    data.directories.forEach((path) => {
      const item = document.createElement("li");
      item.textContent = path;
      directoryList.append(item);
    });
    emptySummary.textContent = data.directories.length
      ? `发现 ${data.directories.length} 个可删除的空文件夹。`
      : "没有发现空文件夹。";
    renderErrors(emptyErrors, data.errors);
    emptyDeleteButton.classList.toggle("hidden", data.directories.length === 0);
    emptyResults.classList.remove("hidden");
    clearStatus(emptyStatus);
  } catch (error) {
    setStatus(emptyStatus, error.message, "error");
  } finally {
    submit.disabled = false;
  }
});

emptyDeleteButton.addEventListener("click", async () => {
  if (!emptyScanToken) return;
  if (!window.confirm("确定删除扫描结果中的空文件夹吗？扫描根目录永远不会被删除。")) return;
  emptyDeleteButton.disabled = true;
  setStatus(emptyStatus, "正在重新检查并删除空文件夹…");
  try {
    const data = await postJson(appUrl("api/empty-directories/delete"), {scan_token: emptyScanToken});
    emptyScanToken = null;
    emptyDeleteButton.classList.add("hidden");
    setStatus(emptyStatus, `已删除 ${data.deleted_count} 个空文件夹。`, "success");
    renderErrors(emptyErrors, data.errors);
    directoryList.replaceChildren();
    data.deleted.forEach((path) => {
      const item = document.createElement("li");
      item.textContent = path;
      directoryList.append(item);
    });
    emptySummary.textContent = "删除操作已完成。";
  } catch (error) {
    setStatus(emptyStatus, error.message, "error");
  } finally {
    emptyDeleteButton.disabled = false;
  }
});
