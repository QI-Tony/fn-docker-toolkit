const duplicateForm = document.querySelector("#scan-form");
const duplicateStatus = document.querySelector("#status");
const duplicateResults = document.querySelector("#results");
const duplicateSummary = document.querySelector("#summary");
const duplicateErrors = document.querySelector("#error-list");
const groupList = document.querySelector("#group-list");
const duplicateDeleteButton = document.querySelector("#delete-button");
let duplicateScanToken = null;
let duplicateGroups = [];

function statCard(label, value) {
  const card = document.createElement("div");
  card.className = "stat-card";
  const number = document.createElement("strong");
  number.textContent = value;
  const caption = document.createElement("span");
  caption.textContent = label;
  card.append(number, caption);
  return card;
}

function renderGroups(groups) {
  groupList.replaceChildren();
  groups.forEach((group, groupIndex) => {
    const card = document.createElement("section");
    card.className = "duplicate-group panel";
    const heading = document.createElement("div");
    heading.className = "group-heading";
    const title = document.createElement("h3");
    title.textContent = `重复组 ${groupIndex + 1}`;
    const meta = document.createElement("span");
    meta.textContent = `${formatBytes(group.size)} · MD5 ${group.md5}`;
    heading.append(title, meta);
    card.append(heading);

    group.files.forEach((path, fileIndex) => {
      const label = document.createElement("label");
      label.className = "file-choice";
      const radio = document.createElement("input");
      radio.type = "radio";
      radio.name = `keep-${groupIndex}`;
      radio.value = path;
      radio.checked = fileIndex === 0;
      const text = document.createElement("span");
      text.textContent = path;
      label.append(radio, text);
      card.append(label);
    });
    groupList.append(card);
  });
}

duplicateForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  duplicateResults.classList.add("hidden");
  duplicateDeleteButton.classList.add("hidden");
  duplicateScanToken = null;
  duplicateGroups = [];
  setStatus(duplicateStatus, "正在统计文件并计算候选文件 MD5…");
  const submit = duplicateForm.querySelector("button[type=submit]");
  submit.disabled = true;
  try {
    const data = await postJson(appUrl("api/duplicates/scan"), {
      path: document.querySelector("#path").value,
    });
    duplicateScanToken = data.scan_token;
    duplicateGroups = data.groups;
    duplicateSummary.replaceChildren(
      statCard("扫描文件", data.scanned_files),
      statCard("重复文件组", data.duplicate_groups),
      statCard("可删除副本", data.duplicate_files),
      statCard("预计可释放", formatBytes(data.reclaimable_bytes)),
    );
    renderErrors(duplicateErrors, data.errors);
    renderGroups(data.groups);
    duplicateDeleteButton.classList.toggle("hidden", data.groups.length === 0);
    duplicateResults.classList.remove("hidden");
    clearStatus(duplicateStatus);
  } catch (error) {
    setStatus(duplicateStatus, error.message, "error");
  } finally {
    submit.disabled = false;
  }
});

duplicateDeleteButton.addEventListener("click", async () => {
  if (!duplicateScanToken) return;
  const selections = duplicateGroups.map((group, index) => ({
    group_id: group.id,
    keep_path: document.querySelector(`input[name="keep-${index}"]:checked`).value,
  }));
  const count = duplicateGroups.reduce((total, group) => total + group.files.length - 1, 0);
  if (!window.confirm(`将保留每组所选文件，并删除其余 ${count} 个副本。确定继续吗？删除前会重新验证内容。`)) return;
  duplicateDeleteButton.disabled = true;
  setStatus(duplicateStatus, "正在重新验证文件并删除副本…");
  try {
    const data = await postJson(appUrl("api/duplicates/delete"), {
      scan_token: duplicateScanToken,
      selections,
    });
    duplicateScanToken = null;
    duplicateDeleteButton.classList.add("hidden");
    setStatus(duplicateStatus, `已删除 ${data.deleted_count} 个文件，释放 ${formatBytes(data.reclaimed_bytes)}。`, "success");
    renderErrors(duplicateErrors, data.errors);
  } catch (error) {
    setStatus(duplicateStatus, error.message, "error");
  } finally {
    duplicateDeleteButton.disabled = false;
  }
});
