(() => {
  "use strict";

  const STORAGE_KEY = "svnlab.connection.v1";
  const MODE_KEY = "svnlab.diff-mode.v1";
  const view = document.querySelector("#view");
  const connectionDot = document.querySelector("#connection-dot");
  const connectionLabel = document.querySelector("#connection-label");
  const projectName = document.querySelector("#project-name");
  const toastRegion = document.querySelector("#toast-region");

  const state = {
    connection: loadConnection(),
    routeEpoch: 0,
    commits: [],
    nextBefore: null,
    cursor: null,
    cursorHistory: [],
    detail: null,
    diffMode: localStorage.getItem(MODE_KEY) || (matchMedia("(max-width: 740px)").matches ? "unified" : "split"),
    fileViews: new Map(),
    contexts: new Map(),
  };

  class ApiError extends Error {
    constructor(payload, status) {
      super(payload?.message || `请求失败（HTTP ${status}）`);
      this.code = payload?.error || "request_failed";
      this.hint = payload?.hint || "";
      this.status = status;
    }
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function button(label, className = "button") {
    const node = el("button", className, label);
    node.type = "button";
    return node;
  }

  function loadConnection() {
    try {
      const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
      if (parsed && typeof parsed.repository === "string") return parsed;
    } catch (_) {
      // A damaged local value is treated as an empty first run.
    }
    return null;
  }

  function saveConnection(connection) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(connection));
    state.connection = connection;
    updateConnectionChrome();
  }

  function repositoryLabel(repository) {
    try {
      const url = new URL(repository);
      const segments = url.pathname.split("/").filter(Boolean);
      return decodeURIComponent(segments.at(-1) || url.hostname || "SVN 仓库");
    } catch (_) {
      return "SVN 仓库";
    }
  }

  function updateConnectionChrome() {
    if (!state.connection) {
      connectionDot.classList.remove("online");
      connectionLabel.textContent = "尚未连接";
      projectName.textContent = "SVN 仓库";
      return;
    }
    connectionDot.classList.add("online");
    const label = repositoryLabel(state.connection.repository);
    connectionLabel.textContent = label;
    connectionLabel.title = state.connection.repository;
    projectName.textContent = label;
  }

  async function post(path, payload) {
    let response;
    try {
      response = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        cache: "no-store",
        body: JSON.stringify(payload),
      });
    } catch (_) {
      throw new ApiError({ message: "无法连接 SVNLab 后端。", hint: "确认服务仍在运行后重试。" }, 0);
    }
    let body = null;
    try {
      body = await response.json();
    } catch (_) {
      body = { message: "后端返回了无法识别的响应。" };
    }
    if (!response.ok) throw new ApiError(body, response.status);
    return body;
  }

  function toast(message, kind = "normal") {
    const item = el("div", `toast${kind === "error" ? " error" : ""}`, message);
    toastRegion.append(item);
    window.setTimeout(() => item.remove(), 3600);
  }

  function errorAlert(error) {
    const box = el("div", "alert");
    const marker = el("strong", null, "!");
    marker.setAttribute("aria-hidden", "true");
    const copy = el("div");
    copy.append(el("strong", null, error.message || "请求失败"));
    if (error.hint) copy.append(el("p", "hint", error.hint));
    box.append(marker, copy);
    return box;
  }

  function contentWrap(...children) {
    const wrap = el("div", "content-wrap");
    wrap.append(...children);
    return wrap;
  }

  function breadcrumb(items) {
    const node = el("nav", "breadcrumb");
    node.setAttribute("aria-label", "面包屑");
    items.forEach((item, index) => {
      if (index) node.append(el("span", null, "/"));
      if (item.href) {
        const link = el("a", null, item.label);
        link.href = item.href;
        node.append(link);
      } else {
        node.append(el("span", null, item.label));
      }
    });
    return node;
  }

  function setActiveNav(name) {
    document.querySelectorAll("[data-nav]").forEach((link) => {
      link.classList.toggle("active", link.dataset.nav === name);
    });
  }

  function renderSkeleton(title = "正在读取仓库…") {
    const heading = el("div", "page-header");
    const copy = el("div");
    copy.append(el("h1", "page-heading", title), el("p", "page-subtitle", "SVNLab 正在通过本机 SVN 客户端获取数据。"));
    heading.append(copy);
    const panel = el("div", "panel skeleton");
    for (let i = 0; i < 5; i += 1) {
      const row = el("div", "skeleton-row");
      const lines = el("div", "skeleton-lines");
      lines.append(el("div", "skeleton-line"), el("div", "skeleton-line"));
      row.append(el("div", "skeleton-circle"), lines);
      panel.append(row);
    }
    view.replaceChildren(contentWrap(heading, panel));
  }

  function renderSettings() {
    setActiveNav("settings");
    const shell = el("div", "setup-shell");
    const card = el("section", "panel setup-card");
    const hero = el("div", "setup-hero");
    hero.append(
      el("div", "setup-kicker", state.connection ? "Repository connection" : "Start here"),
      el("h1", null, state.connection ? "更新仓库连接" : "连接你的 SVN 仓库"),
      el("p", null, "使用本机 SVN 客户端读取提交、完整 diff 和文件内容。SVNLab 不会修改仓库。"),
    );

    const form = el("form", "setup-form");
    const errorSlot = el("div");
    const repoField = field("仓库地址", "repository", "https://svn.example.com/repos/project/trunk", "支持 file://、svn:// 和 HTTP(S) 地址");
    repoField.input.required = true;
    repoField.input.value = state.connection?.repository || "";
    const userField = field("用户名", "username", "svn-user");
    userField.input.value = state.connection?.username || "";
    const passwordField = field("密码", "password", "输入 SVN 密码");
    passwordField.input.type = "password";
    passwordField.input.value = state.connection?.password || "";
    const credentials = el("div", "field-row");
    credentials.append(userField.wrapper, passwordField.wrapper);

    const actions = el("div", "form-actions");
    const submit = button("测试连接并进入", "button primary");
    submit.type = "submit";
    actions.append(submit);
    if (state.connection) {
      const cancel = el("a", "button", "返回提交记录");
      cancel.href = "#/commits";
      actions.append(cancel);
    }

    const privacy = el("p", "privacy-note", "凭据会保存在当前浏览器的 localStorage 中，并在请求时发送给本机后端。能访问此浏览器配置的人也能读取密码。后端不会将凭据写入文件。 SVN CLI 启动时，密码可能短暂出现在本机进程参数中。");
    form.append(errorSlot, repoField.wrapper, credentials, actions, privacy);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      errorSlot.replaceChildren();
      const connection = {
        repository: repoField.input.value.trim(),
        username: userField.input.value.trim(),
        password: passwordField.input.value,
      };
      submit.disabled = true;
      submit.textContent = "正在测试…";
      try {
        await post("/api/repository/check", { connection });
        saveConnection(connection);
        toast("仓库连接成功");
        location.hash = "#/commits";
      } catch (error) {
        errorSlot.append(errorAlert(error));
      } finally {
        submit.disabled = false;
        submit.textContent = "测试连接并进入";
      }
    });

    card.append(hero, form);
    shell.append(card);
    view.replaceChildren(contentWrap(shell));
    repoField.input.focus();
  }

  function field(labelText, name, placeholder, hint = "") {
    const wrapper = el("div", "field");
    const label = el("label", null, labelText);
    const input = el("input");
    input.name = name;
    input.id = `field-${name}`;
    input.placeholder = placeholder;
    input.autocomplete = name === "password" ? "current-password" : "off";
    label.htmlFor = input.id;
    wrapper.append(label, input);
    if (hint) wrapper.append(el("div", "field-hint", hint));
    return { wrapper, input };
  }

  async function renderCommits(epoch) {
    setActiveNav("commits");
    renderSkeleton("提交记录");
    try {
      const result = await post("/api/commits", {
        connection: state.connection,
        limit: 30,
        before_revision: state.cursor,
      });
      if (epoch !== state.routeEpoch) return;
      state.commits = result.commits;
      state.nextBefore = result.next_before;
      drawCommitList();
    } catch (error) {
      if (epoch !== state.routeEpoch) return;
      drawPageError("无法读取提交记录", error);
    }
  }

  function drawCommitList() {
    const header = el("div", "page-header");
    const headingCopy = el("div");
    headingCopy.append(
      el("h1", "page-heading", "提交记录"),
      el("p", "page-subtitle", state.connection.repository),
    );
    const actions = el("div", "header-actions");
    const refresh = button("刷新");
    refresh.addEventListener("click", () => route());
    actions.append(refresh);
    header.append(headingCopy, actions);

    const panel = el("section", "panel commit-list");
    if (!state.commits.length) {
      const empty = el("div", "empty-state");
      empty.append(el("div", "empty-state-mark", "r—"), el("h2", null, "暂无提交"), el("p", null, "该路径中没有可显示的提交记录。"));
      panel.append(empty);
    } else {
      state.commits.forEach((commit) => panel.append(commitRow(commit)));
    }

    const pager = el("div", "pagination");
    const newer = button("较新的提交");
    newer.disabled = state.cursorHistory.length === 0;
    newer.addEventListener("click", () => {
      state.cursor = state.cursorHistory.pop() ?? null;
      route();
    });
    const older = button("更早的提交");
    older.disabled = state.nextBefore === null;
    older.addEventListener("click", () => {
      state.cursorHistory.push(state.cursor);
      state.cursor = state.nextBefore;
      route();
    });
    pager.append(newer, older);
    view.replaceChildren(contentWrap(breadcrumb([{ label: repositoryLabel(state.connection.repository) }, { label: "提交记录" }]), header, panel, pager));
  }

  function commitRow(commit) {
    const row = el("a", "commit-row");
    row.href = `#/commits/${commit.revision}`;
    const avatar = el("span", "author-avatar", initials(commit.author));
    const copy = el("span", "commit-copy");
    const firstLine = (commit.message || "无提交说明").split(/\r?\n/, 1)[0];
    const message = el("span", "commit-message", firstLine);
    const meta = el("span", "commit-meta");
    meta.append(el("span", null, commit.author || "未知作者"), el("span", null, formatDate(commit.date)));
    copy.append(message, meta);
    const tail = el("span", "commit-tail");
    tail.append(el("span", "file-count", `${commit.changed_file_count} 个文件`), el("span", "revision-chip", `r${commit.revision}`));
    row.append(avatar, copy, tail);
    return row;
  }

  function initials(author) {
    const clean = (author || "?").trim();
    if (!clean) return "?";
    const parts = clean.split(/[\s._-]+/).filter(Boolean);
    return parts.slice(0, 2).map((part) => part[0]).join("").toUpperCase();
  }

  function formatDate(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value || "未知时间";
    return new Intl.DateTimeFormat("zh-CN", {
      year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", hour12: false,
    }).format(date);
  }

  async function renderRevision(revision, epoch) {
    setActiveNav("commits");
    renderSkeleton(`正在读取 r${revision}…`);
    state.fileViews.clear();
    state.contexts.clear();
    try {
      const result = await post(`/api/commits/${revision}`, { connection: state.connection });
      if (epoch !== state.routeEpoch) return;
      state.detail = result;
      drawRevision();
    } catch (error) {
      if (epoch !== state.routeEpoch) return;
      drawPageError(`无法读取 r${revision}`, error);
    }
  }

  function drawRevision(options = {}) {
    const { preserveScroll = false } = options;
    const oldScroll = window.scrollY;
    const commit = state.detail.revision;
    const header = el("div", "page-header revision-header");
    const rail = el("div", "revision-rail");
    rail.append(el("span", null, "REV"), el("strong", null, `r${commit.revision}`));
    const headingCopy = el("div");
    const messageParts = (commit.message || "无提交说明").split(/\r?\n/);
    const title = messageParts.shift() || "无提交说明";
    headingCopy.append(el("h1", "page-heading revision-message", title));
    const description = messageParts.join("\n").trim();
    if (description) headingCopy.append(el("p", "revision-description", description));
    const meta = el("div", "revision-meta");
    const author = el("span");
    author.append(el("b", null, commit.author || "未知作者"), document.createTextNode(" 提交"));
    meta.append(author, el("span", null, formatDate(commit.date)), el("span", null, `${state.detail.diffs.length} 个变更文件`));
    headingCopy.append(meta);
    const actions = el("div", "header-actions");
    actions.append(modeSwitch());
    header.append(rail, headingCopy, actions);

    const layout = el("div", "review-layout");
    const fileRail = el("nav", "file-rail");
    fileRail.setAttribute("aria-label", "本次变更文件");
    fileRail.append(el("div", "file-rail-head", `本次变更 · ${state.detail.diffs.length}`));
    const stack = el("div", "diff-stack");

    state.detail.diffs.forEach((file, index) => {
      const link = el("a");
      link.href = `#diff-file-${index}`;
      const badge = statusBadge(file.status);
      const path = el("span", "file-rail-path", file.path);
      path.title = file.path;
      link.append(badge, path);
      fileRail.append(link);
      stack.append(renderDiffFile(file, index));
    });

    if (!state.detail.diffs.length) {
      const empty = el("div", "panel empty-state");
      empty.append(el("div", "empty-state-mark", "0"), el("h2", null, "该版本没有文本差异"), el("p", null, "提交可能仅包含仓库元数据变化。"));
      stack.append(empty);
    }

    layout.append(fileRail, stack);
    view.replaceChildren(contentWrap(
      breadcrumb([
        { label: repositoryLabel(state.connection.repository), href: "#/commits" },
        { label: "提交记录", href: "#/commits" },
        { label: `r${commit.revision}` },
      ]),
      header,
      layout,
    ));
    if (preserveScroll) requestAnimationFrame(() => window.scrollTo(0, oldScroll));
  }

  function modeSwitch() {
    const group = el("div", "mode-switch");
    group.setAttribute("aria-label", "Diff 显示模式");
    for (const [mode, label] of [["split", "并排"], ["unified", "单栏"]]) {
      const control = button(label, mode === state.diffMode ? "active" : "");
      control.setAttribute("aria-pressed", String(mode === state.diffMode));
      control.addEventListener("click", () => {
        if (state.diffMode === mode) return;
        state.diffMode = mode;
        localStorage.setItem(MODE_KEY, mode);
        drawRevision({ preserveScroll: true });
      });
      group.append(control);
    }
    return group;
  }

  function statusBadge(status) {
    const labels = { added: "A", deleted: "D", modified: "M", replaced: "R", property: "P", binary: "B", unknown: "?" };
    return el("span", `file-status status-${status}`, labels[status] || "?");
  }

  function renderDiffFile(file, index) {
    const section = el("section", "diff-file");
    section.id = `diff-file-${index}`;
    const header = el("header", "diff-file-header");
    header.append(statusBadge(file.status));
    const path = el("span", "diff-path", file.path);
    path.title = file.path;
    header.append(path);
    const stats = diffStats(file);
    const statNode = el("span", "diff-stats");
    statNode.append(el("span", "stat-add", `+${stats.additions}`), el("span", "stat-del", `−${stats.deletions}`));
    header.append(statNode);
    const viewButton = button(state.fileViews.get(index)?.active ? "返回差异" : "查看文件", `file-view-button${state.fileViews.get(index)?.active ? " active" : ""}`);
    viewButton.addEventListener("click", () => toggleFileView(index));
    header.append(viewButton);
    section.append(header);

    const fileView = state.fileViews.get(index);
    if (fileView?.active) {
      section.append(renderSourceReader(file, index, fileView));
    } else if (file.binary) {
      const special = el("div", "special-diff");
      special.append(el("strong", null, "二进制文件已变更"), el("span", null, "SVN 无法生成可阅读的文本差异。"));
      section.append(special);
    } else if (file.hunks.length) {
      section.append(state.diffMode === "split" ? renderSplitDiff(file, index) : renderUnifiedDiff(file, index));
    } else {
      const special = el("div", "special-diff");
      special.append(el("strong", null, statusText(file.status)), el("span", null, file.property_changes.length ? "该文件仅包含属性变化。" : "该文件没有可显示的文本行。"));
      section.append(special);
    }
    appendSupplementaryBlocks(section, file);
    return section;
  }

  function diffStats(file) {
    let additions = 0;
    let deletions = 0;
    file.hunks.forEach((hunk) => hunk.lines.forEach((line) => {
      if (line.kind === "addition") additions += 1;
      if (line.kind === "deletion") deletions += 1;
    }));
    return { additions, deletions };
  }

  function statusText(status) {
    return ({ added: "新增文件", deleted: "删除文件", replaced: "替换文件", property: "属性已变更", binary: "二进制文件已变更", modified: "文件已修改" })[status] || "文件已变更";
  }

  function appendSupplementaryBlocks(section, file) {
    if (file.property_changes?.length) {
      const block = el("pre", "property-block");
      block.textContent = file.property_changes.join("\n").trim();
      section.append(block);
    }
    if (file.raw_fallback?.length) {
      const useful = file.raw_fallback.filter((line) => line.trim());
      if (useful.length) {
        const block = el("pre", "raw-block");
        block.textContent = useful.join("\n");
        section.append(block);
      }
    }
  }

  function renderUnifiedDiff(file, fileIndex) {
    const container = el("div", "diff-unified");
    let previous = null;
    file.hunks.forEach((hunk, hunkIndex) => {
      const gap = gapBefore(previous, hunk);
      if (gap) container.append(renderContextGap(file, fileIndex, hunkIndex, gap, "unified"));
      container.append(el("div", "hunk-header", hunk.header));
      hunk.lines.forEach((line) => container.append(unifiedLine(line)));
      previous = hunk;
    });
    if (previous) container.append(renderContextGap(file, fileIndex, file.hunks.length, gapAfter(previous), "unified"));
    return container;
  }

  function unifiedLine(line) {
    const row = el("div", `code-row ${line.kind}`);
    row.append(
      el("span", "line-number", line.old_line ?? ""),
      el("span", "line-number", line.new_line ?? ""),
      el("span", "line-content", line.content),
    );
    return row;
  }

  function renderSplitDiff(file, fileIndex) {
    const container = el("div", "diff-split");
    const head = el("div", "split-head");
    head.append(el("span", null, `r${Math.max(0, state.detail.revision.revision - 1)} · 变更前`), el("span", null, `r${state.detail.revision.revision} · 变更后`));
    container.append(head);
    let previous = null;
    file.hunks.forEach((hunk, hunkIndex) => {
      const gap = gapBefore(previous, hunk);
      if (gap) container.append(renderContextGap(file, fileIndex, hunkIndex, gap, "split"));
      container.append(el("div", "hunk-header", hunk.header));
      buildSplitRows(hunk.lines).forEach(([oldLine, newLine]) => container.append(splitRow(oldLine, newLine)));
      previous = hunk;
    });
    if (previous) container.append(renderContextGap(file, fileIndex, file.hunks.length, gapAfter(previous), "split"));
    return container;
  }

  function buildSplitRows(lines) {
    const rows = [];
    let index = 0;
    while (index < lines.length) {
      const line = lines[index];
      if (line.kind === "context") {
        rows.push([line, line]);
        index += 1;
        continue;
      }
      if (line.kind === "meta") {
        rows.push([line, line]);
        index += 1;
        continue;
      }
      const deletions = [];
      const additions = [];
      while (index < lines.length && !["context", "meta"].includes(lines[index].kind)) {
        if (lines[index].kind === "deletion") deletions.push(lines[index]);
        if (lines[index].kind === "addition") additions.push(lines[index]);
        index += 1;
      }
      const count = Math.max(deletions.length, additions.length);
      for (let cursor = 0; cursor < count; cursor += 1) rows.push([deletions[cursor] || null, additions[cursor] || null]);
    }
    return rows;
  }

  function splitRow(oldLine, newLine) {
    const row = el("div", "split-row");
    row.append(splitCell(oldLine, "old"), splitCell(newLine, "new"));
    return row;
  }

  function splitCell(line, side) {
    if (!line) return el("div", "split-cell empty");
    const number = side === "old" ? line.old_line : line.new_line;
    const cell = el("div", `split-cell ${line.kind}`);
    cell.append(el("span", "line-number", number ?? ""), el("span", "line-content", line.content));
    return cell;
  }

  function gapBefore(previous, current) {
    const newStart = previous ? previous.new_start + previous.new_count : 1;
    const newEnd = current.new_start - 1;
    const oldStart = previous ? previous.old_start + previous.old_count : 1;
    const oldEnd = current.old_start - 1;
    if (newEnd < newStart && oldEnd < oldStart) return null;
    return { sourceStart: newStart, sourceEnd: newEnd, oldStart, newStart, trailing: false };
  }

  function gapAfter(previous) {
    return {
      sourceStart: previous.new_start + previous.new_count,
      sourceEnd: null,
      oldStart: previous.old_start + previous.old_count,
      newStart: previous.new_start + previous.new_count,
      trailing: true,
    };
  }

  function renderContextGap(file, fileIndex, gapIndex, gap, mode) {
    const fragment = document.createDocumentFragment();
    const key = `${fileIndex}:${gapIndex}`;
    const context = state.contexts.get(key);
    if (context?.lines?.size) fragment.append(renderExpandedContext(context, gap, mode));

    const row = el("div", "context-gap");
    const controls = el("div", "gap-controls");
    for (const [direction, label, title] of [["up", "↑", "向上读取 20 行"], ["both", "↕", "上下各读取 20 行"], ["down", "↓", "向下读取 20 行"]]) {
      const control = button(label, "");
      control.title = title;
      control.setAttribute("aria-label", title);
      control.addEventListener("click", () => expandContext(file, fileIndex, gapIndex, gap, direction));
      controls.append(control);
    }
    const knownEnd = gap.sourceEnd ?? context?.total;
    const amount = knownEnd ? Math.max(0, knownEnd - gap.sourceStart + 1 - (context?.lines?.size || 0)) : null;
    const copy = amount === null ? "继续读取文件末尾的上下文" : amount > 0 ? `隐藏 ${amount} 行未变更内容` : "上下文已全部展开";
    row.append(controls, el("span", "gap-copy", copy));
    fragment.append(row);
    return fragment;
  }

  function renderExpandedContext(context, gap, mode) {
    const wrapper = el("div", "expanded-context");
    const entries = [...context.lines.entries()].sort((a, b) => a[0] - b[0]);
    let previousLine = null;
    entries.forEach(([lineNumber, content]) => {
      if (previousLine !== null && lineNumber > previousLine + 1) {
        wrapper.append(el("div", "hunk-header", `… 仍隐藏 ${lineNumber - previousLine - 1} 行 …`));
      }
      const offset = lineNumber - gap.newStart;
      const oldNumber = gap.oldStart + offset;
      const line = { kind: "context", content, old_line: oldNumber, new_line: lineNumber };
      wrapper.append(mode === "split" ? splitRow(line, line) : unifiedLine(line));
      previousLine = lineNumber;
    });
    return wrapper;
  }

  async function expandContext(file, fileIndex, gapIndex, gap, direction) {
    const key = `${fileIndex}:${gapIndex}`;
    const context = state.contexts.get(key) || { lines: new Map(), total: null };
    state.contexts.set(key, context);
    try {
      if (direction === "down" || direction === "both") {
        const loaded = [...context.lines.keys()];
        const start = Math.max(gap.sourceStart, loaded.length ? Math.max(...loaded) + 1 : gap.sourceStart);
        const end = gap.sourceEnd ?? context.total ?? Number.MAX_SAFE_INTEGER;
        if (start <= end) await loadContextRange(file, start, Math.min(20, end - start + 1), context);
      }
      if (direction === "up" || direction === "both") {
        if (context.total === null && gap.sourceEnd === null) await loadContextRange(file, gap.sourceStart, 1, context);
        const loaded = [...context.lines.keys()];
        const end = Math.min(gap.sourceEnd ?? context.total ?? gap.sourceStart, loaded.length ? Math.min(...loaded) - 1 : (gap.sourceEnd ?? context.total ?? gap.sourceStart));
        const start = Math.max(gap.sourceStart, end - 19);
        if (end >= start) await loadContextRange(file, start, end - start + 1, context);
      }
      drawRevision({ preserveScroll: true });
    } catch (error) {
      toast(error.message, "error");
    }
  }

  async function loadContextRange(file, start, count, context) {
    const response = await requestFileContent(file, start, count);
    response.lines.forEach((line, index) => context.lines.set(response.start_line + index, line));
    context.total = response.total_lines;
  }

  async function toggleFileView(index) {
    const file = state.detail.diffs[index];
    const current = state.fileViews.get(index);
    if (current?.active) {
      current.active = false;
      drawRevision({ preserveScroll: true });
      return;
    }
    if (current) {
      current.active = true;
      drawRevision({ preserveScroll: true });
      return;
    }
    state.fileViews.set(index, { active: true, loading: true, start: 1, end: 0, total: 0, lines: [] });
    drawRevision({ preserveScroll: true });
    try {
      const response = await requestFileContent(file, 1, 200);
      state.fileViews.set(index, { active: true, loading: false, start: response.start_line, end: response.end_line, total: response.total_lines, lines: response.lines });
      drawRevision({ preserveScroll: true });
    } catch (error) {
      state.fileViews.delete(index);
      toast(error.message, "error");
      drawRevision({ preserveScroll: true });
    }
  }

  async function requestFileContent(file, startLine, lineCount) {
    const revision = file.status === "deleted" ? Math.max(0, state.detail.revision.revision - 1) : state.detail.revision.revision;
    return post("/api/files/content", {
      connection: state.connection,
      path: file.path,
      revision,
      start_line: startLine,
      line_count: lineCount,
    });
  }

  function renderSourceReader(file, index, source) {
    const reader = el("div", "source-reader");
    if (source.loading) {
      const loading = el("div", "special-diff");
      loading.append(el("strong", null, "正在读取文件…"), el("span", null, "首次打开会调用 svn cat。"));
      reader.append(loading);
      return reader;
    }
    if (source.start > 1) reader.append(sourceLoadButton(index, "up", `向上读取 ${Math.min(200, source.start - 1)} 行`));
    source.lines.forEach((line, offset) => {
      const row = el("div", "source-row");
      row.append(el("span", "source-line", source.start + offset), el("span", "source-code", line));
      reader.append(row);
    });
    if (source.end < source.total) reader.append(sourceLoadButton(index, "down", `向下读取 ${Math.min(200, source.total - source.end)} 行`));
    return reader;
  }

  function sourceLoadButton(index, direction, label) {
    const control = el("button", "source-load");
    control.type = "button";
    control.append(el("span", null, direction === "up" ? "↑" : "↓"), el("span", null, label));
    control.addEventListener("click", () => loadMoreSource(index, direction));
    return control;
  }

  async function loadMoreSource(index, direction) {
    const source = state.fileViews.get(index);
    const file = state.detail.diffs[index];
    try {
      if (direction === "up") {
        const start = Math.max(1, source.start - 200);
        const response = await requestFileContent(file, start, source.start - start);
        source.lines = [...response.lines, ...source.lines];
        source.start = response.start_line;
      } else {
        const response = await requestFileContent(file, source.end + 1, 200);
        source.lines.push(...response.lines);
        source.end = response.end_line;
        source.total = response.total_lines;
      }
      drawRevision({ preserveScroll: true });
    } catch (error) {
      toast(error.message, "error");
    }
  }

  function drawPageError(title, error) {
    const header = el("div", "page-header");
    const copy = el("div");
    copy.append(el("h1", "page-heading", title), el("p", "page-subtitle", "仓库内容没有被修改。"));
    header.append(copy);
    const retry = button("重试", "button primary");
    retry.addEventListener("click", () => route());
    const settings = el("a", "button", "检查仓库设置");
    settings.href = "#/settings";
    const actions = el("div", "form-actions");
    actions.append(retry, settings);
    view.replaceChildren(contentWrap(header, errorAlert(error), actions));
  }

  async function route() {
    const epoch = ++state.routeEpoch;
    const hash = location.hash || "#/commits";
    if (!state.connection && hash !== "#/settings") {
      location.replace("#/settings");
      return;
    }
    if (hash === "#/settings") {
      renderSettings();
      return;
    }
    const revisionMatch = hash.match(/^#\/commits\/(\d+)$/);
    if (revisionMatch) {
      await renderRevision(Number(revisionMatch[1]), epoch);
      return;
    }
    if (hash !== "#/commits") location.replace("#/commits");
    await renderCommits(epoch);
  }

  document.querySelector("#revision-search").addEventListener("submit", (event) => {
    event.preventDefault();
    const input = document.querySelector("#revision-input");
    const revision = Number(input.value.trim().replace(/^r/i, ""));
    if (!Number.isInteger(revision) || revision < 1) {
      toast("请输入有效的 SVN 版本号", "error");
      return;
    }
    input.value = "";
    location.hash = `#/commits/${revision}`;
  });

  window.addEventListener("hashchange", route);
  updateConnectionChrome();
  route();
})();

