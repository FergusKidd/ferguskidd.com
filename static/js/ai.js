(function () {
  const studio = document.getElementById("studio");
  const form = document.getElementById("composer");
  const log = document.getElementById("transcript");
  const input = document.getElementById("prompt");
  const send = document.getElementById("send");
  const chatList = document.getElementById("chat-list");
  const chatTitle = document.getElementById("chat-title");
  const sheet = document.getElementById("settings-sheet");
  const memoryList = document.getElementById("memory-list");
  if (!studio || !form || !log || !input || !send) return;

  const headers = { "X-Requested-With": "fk-ai" };
  let state = {
    chat_id: "",
    chats: [],
    memories: [],
    settings: {},
  };

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (char) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      }[char])
    );
  }

  function renderMarkdown(source) {
    const fences = [];
    let text = escapeHtml(source).replace(/```([^\n`]*)\n?([\s\S]*?)```/g, (_, _lang, code) => {
      const index = fences.length;
      fences.push("<pre><code>" + code.replace(/\n$/, "") + "</code></pre>");
      return "%%FENCE" + index + "%%";
    });
    text = text.replace(/`([^`]+)`/g, "<code>$1</code>");
    text = text.replace(
      /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
    );
    text = text.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    text = text.replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>");

    const html = text
      .split(/\n{2,}/)
      .map((block) => {
        const trimmed = block.trim();
        if (!trimmed) return "";
        const fenceOnly = trimmed.match(/^%%FENCE(\d+)%%$/);
        if (fenceOnly) return fences[Number(fenceOnly[1])] || "";
        const lines = trimmed.split("\n");
        if (lines.every((line) => /^[-*]\s+/.test(line.trim()))) {
          return (
            "<ul>" +
            lines.map((line) => "<li>" + line.trim().replace(/^[-*]\s+/, "") + "</li>").join("") +
            "</ul>"
          );
        }
        if (lines.every((line) => /^\d+\.\s+/.test(line.trim()))) {
          return (
            "<ol>" +
            lines.map((line) => "<li>" + line.trim().replace(/^\d+\.\s+/, "") + "</li>").join("") +
            "</ol>"
          );
        }
        if (trimmed.startsWith("### ")) return "<h3>" + trimmed.slice(4) + "</h3>";
        if (trimmed.startsWith("## ")) return "<h3>" + trimmed.slice(3) + "</h3>";
        return "<p>" + trimmed.replace(/\n/g, "<br>") + "</p>";
      })
      .join("");

    return html.replace(/%%FENCE(\d+)%%/g, (_, index) => fences[Number(index)] || "");
  }

  function appendMessage(role, text) {
    const empty = document.getElementById("empty-state");
    if (empty) empty.remove();
    const article = document.createElement("article");
    article.className = "msg msg--" + role;
    if (role === "user") {
      const paragraph = document.createElement("p");
      paragraph.textContent = text;
      article.appendChild(paragraph);
    } else {
      article.innerHTML = text ? renderMarkdown(text) : "";
    }
    log.appendChild(article);
    log.scrollTop = log.scrollHeight;
    return article;
  }

  function renderTranscript(messages) {
    log.replaceChildren();
    if (!messages || !messages.length) {
      const note = document.createElement("div");
      note.id = "empty-state";
      note.className = "empty-state";
      note.textContent = "Ask for a draft, a critique, a plan, or a second opinion.";
      log.appendChild(note);
      return;
    }
    messages.forEach((item) => appendMessage(item.role, item.content));
  }

  function relativeTime(stamp) {
    const seconds = Math.max(0, Math.floor(Date.now() / 1000 - Number(stamp || 0)));
    if (seconds < 60) return "just now";
    if (seconds < 3600) return Math.floor(seconds / 60) + "m";
    if (seconds < 86400) return Math.floor(seconds / 3600) + "h";
    if (seconds < 604800) return Math.floor(seconds / 86400) + "d";
    return new Date(Number(stamp) * 1000).toLocaleDateString();
  }

  function renderChats() {
    if (!chatList) return;
    chatList.replaceChildren();
    if (!state.chats.length) {
      const empty = document.createElement("p");
      empty.className = "rail-empty";
      empty.textContent = "No saved chats yet.";
      chatList.appendChild(empty);
      return;
    }
    state.chats.forEach((chat) => {
      const row = document.createElement("div");
      row.className = "chat-item" + (chat.id === state.chat_id ? " is-active" : "");
      const open = document.createElement("button");
      open.type = "button";
      open.className = "chat-open";
      open.innerHTML =
        "<strong>" +
        escapeHtml(chat.title || "New chat") +
        "</strong><span>" +
        escapeHtml(relativeTime(chat.updated)) +
        "</span>";
      open.addEventListener("click", () => openChat(chat.id));
      const del = document.createElement("button");
      del.type = "button";
      del.className = "chat-delete";
      del.setAttribute("aria-label", "Delete chat");
      del.textContent = "×";
      del.addEventListener("click", (event) => {
        event.stopPropagation();
        deleteChat(chat.id);
      });
      row.append(open, del);
      chatList.appendChild(row);
    });
    const active = state.chats.find((chat) => chat.id === state.chat_id);
    if (chatTitle) chatTitle.textContent = active ? active.title || "Studio" : "Studio";
  }

  function renderMemories() {
    if (!memoryList) return;
    memoryList.replaceChildren();
    if (!state.memories.length) {
      const empty = document.createElement("p");
      empty.className = "rail-empty";
      empty.textContent = "Nothing stored yet. Pin a note, or let chats teach the studio.";
      memoryList.appendChild(empty);
      return;
    }
    state.memories.forEach((memory) => {
      const row = document.createElement("article");
      row.className = "memory-item";
      row.innerHTML =
        "<p><span class=\"memory-kind\">" +
        escapeHtml(memory.kind || "fact") +
        (memory.pinned ? " · pinned" : "") +
        "</span>" +
        escapeHtml(memory.text || "") +
        "</p>";
      const actions = document.createElement("div");
      actions.className = "memory-actions";
      const pin = document.createElement("button");
      pin.type = "button";
      pin.className = "btn btn-ghost btn-compact";
      pin.textContent = memory.pinned ? "Unpin" : "Pin";
      pin.addEventListener("click", () => pinMemory(memory.id, !memory.pinned));
      const forget = document.createElement("button");
      forget.type = "button";
      forget.className = "btn btn-ghost btn-compact";
      forget.textContent = "Forget";
      forget.addEventListener("click", () => forgetMemory(memory.id));
      actions.append(pin, forget);
      row.appendChild(actions);
      memoryList.appendChild(row);
    });
  }

  function fillSettings() {
    const retention = document.getElementById("retention-days");
    const memoryEnabled = document.getElementById("memory-enabled");
    const autoTitle = document.getElementById("auto-title");
    const backend = document.getElementById("backend-pill");
    if (retention) retention.value = state.settings.retention_days || 90;
    if (memoryEnabled) memoryEnabled.checked = !!state.settings.memory_enabled;
    if (autoTitle) autoTitle.checked = !!state.settings.auto_title;
    if (backend) {
      backend.textContent =
        state.settings.backend === "azure"
          ? "Storage: Azure tables + blobs"
          : "Storage: local fallback (set AZURE_CONNECTION_STRING for cloud history)";
    }
  }

  async function api(url, options) {
    const response = await fetch(url, {
      ...options,
      headers: {
        ...headers,
        ...(options && options.headers ? options.headers : {}),
      },
    });
    if (response.status === 401) {
      window.location.assign("/ai");
      return null;
    }
    let data = null;
    try {
      data = await response.json();
    } catch (err) {
      data = null;
    }
    if (!response.ok) {
      throw new Error((data && data.error) || "Request failed.");
    }
    return data;
  }

  async function loadState() {
    const data = await api("/ai/api/state", { method: "GET" });
    if (!data) return;
    state.chat_id = data.chat_id;
    state.chats = data.chats || [];
    state.memories = data.memories || [];
    state.settings = data.settings || {};
    renderTranscript(data.messages || []);
    renderChats();
    renderMemories();
    fillSettings();
  }

  async function openChat(chatId) {
    if (!chatId || chatId === state.chat_id) return;
    const data = await api("/ai/api/chats/open", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: chatId }),
    });
    if (!data) return;
    state.chat_id = data.chat_id;
    state.chats = data.chats || state.chats;
    renderTranscript(data.messages || []);
    renderChats();
  }

  async function deleteChat(chatId) {
    if (!chatId || !window.confirm("Delete this chat?")) return;
    const data = await api("/ai/api/chats/" + encodeURIComponent(chatId), { method: "DELETE" });
    if (!data) return;
    state.chat_id = data.chat_id;
    state.chats = data.chats || [];
    renderTranscript(data.messages || []);
    renderChats();
  }

  async function pinMemory(id, pinned) {
    const data = await api("/ai/api/memories/" + encodeURIComponent(id) + "/pin", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pinned: !!pinned }),
    });
    if (!data) return;
    state.memories = data.memories || [];
    renderMemories();
  }

  async function forgetMemory(id) {
    const data = await api("/ai/api/memories/" + encodeURIComponent(id), { method: "DELETE" });
    if (!data) return;
    state.memories = data.memories || [];
    renderMemories();
  }

  function grow() {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 180) + "px";
  }

  input.addEventListener("input", grow);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const text = input.value.trim();
    if (!text || send.disabled) return;
    input.value = "";
    grow();
    appendMessage("user", text);
    const pending = appendMessage("assistant", "");
    pending.classList.add("is-streaming");
    pending.setAttribute("aria-busy", "true");
    send.disabled = true;
    let full = "";
    let frame = 0;

    const paint = () => {
      pending.innerHTML = renderMarkdown(full) + '<span class="caret" aria-hidden="true"></span>';
      log.scrollTop = log.scrollHeight;
    };

    try {
      const response = await fetch("/ai/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "fk-ai",
        },
        body: JSON.stringify({ message: text }),
      });
      if (response.status === 401) {
        window.location.assign("/ai");
        return;
      }
      if (!response.ok || !response.body) {
        let detail = "Couldn't reach the studio.";
        try {
          const data = await response.json();
          if (data && data.error) detail = data.error;
        } catch (err) {
          /* keep the fallback */
        }
        const paragraph = document.createElement("p");
        paragraph.textContent = detail;
        pending.replaceChildren(paragraph);
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";
        for (const part of parts) {
          const line = part
            .split("\n")
            .filter((item) => item.startsWith("data:"))
            .map((item) => item.slice(5).trim())
            .join("");
          if (!line) continue;
          let data;
          try {
            data = JSON.parse(line);
          } catch (err) {
            continue;
          }
          if (data.status && !full) {
            pending.innerHTML =
              '<p class="msg-status">' +
              escapeHtml(data.status) +
              '</p><span class="caret" aria-hidden="true"></span>';
            log.scrollTop = log.scrollHeight;
          }
          if (data.token) {
            full += data.token;
            if (!frame) {
              frame = requestAnimationFrame(() => {
                frame = 0;
                paint();
              });
            }
          }
          if (data.error) {
            full = "";
            const paragraph = document.createElement("p");
            paragraph.textContent = data.error;
            pending.replaceChildren(paragraph);
          }
        }
      }
      if (full) pending.innerHTML = renderMarkdown(full);
      await loadState();
    } catch (err) {
      const paragraph = document.createElement("p");
      paragraph.textContent = "The connection dropped.";
      pending.replaceChildren(paragraph);
    } finally {
      if (frame) cancelAnimationFrame(frame);
      pending.classList.remove("is-streaming");
      pending.removeAttribute("aria-busy");
      send.disabled = false;
      input.focus();
    }
  });

  document.getElementById("new-chat")?.addEventListener("click", async () => {
    const data = await api("/ai/api/reset", { method: "POST" });
    if (!data) return;
    state.chat_id = data.chat_id;
    await loadState();
    input.focus();
  });

  document.getElementById("open-settings")?.addEventListener("click", () => {
    fillSettings();
    sheet?.showModal();
  });

  document.getElementById("save-settings")?.addEventListener("click", async () => {
    const data = await api("/ai/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        retention_days: Number(document.getElementById("retention-days")?.value || 90),
        memory_enabled: !!document.getElementById("memory-enabled")?.checked,
        auto_title: !!document.getElementById("auto-title")?.checked,
      }),
    });
    if (!data) return;
    state.settings = data.settings || state.settings;
    fillSettings();
  });

  document.getElementById("clear-memories")?.addEventListener("click", async () => {
    if (!window.confirm("Clear all memories?")) return;
    const data = await api("/ai/api/memories", { method: "DELETE" });
    if (!data) return;
    state.memories = [];
    renderMemories();
  });

  document.getElementById("memory-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const field = document.getElementById("memory-text");
    const text = field?.value.trim();
    if (!text) return;
    const data = await api("/ai/api/memories", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, kind: "fact" }),
    });
    if (!data) return;
    field.value = "";
    state.memories = data.memories || [];
    renderMemories();
  });

  loadState().catch(() => {
    const note = document.getElementById("empty-state");
    if (note) note.textContent = "Could not load history. Refresh and try again.";
  });
})();
