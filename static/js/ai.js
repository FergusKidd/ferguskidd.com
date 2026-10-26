(function () {
  const form = document.getElementById("composer");
  const log = document.getElementById("transcript");
  const input = document.getElementById("prompt");
  const send = document.getElementById("send");
  if (!form || !log || !input || !send) return;

  const empty = document.getElementById("empty-state");

  function escapeHtml(value) {
    return value.replace(/[&<>"']/g, (char) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    }[char]));
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
    const response = await fetch("/ai/api/reset", {
      method: "POST",
      headers: { "X-Requested-With": "fk-ai" },
    });
    if (response.status === 401) {
      window.location.assign("/ai");
      return;
    }
    log.replaceChildren();
    const note = document.createElement("div");
    note.id = "empty-state";
    note.className = "empty-state";
    note.textContent = "Fresh thread. Ask for a draft, a critique, or a second opinion.";
    log.appendChild(note);
    input.focus();
  });
})();
