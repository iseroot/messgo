(() => {
    const state = {
        currentChatId: null,
        currentChatTitle: "",
        reconnectDelayMs: 1000,
        ws: null,
    };

    const csrfCookieName = "messgo_csrf_token";

    function getCookie(name) {
        const parts = document.cookie.split(";").map((item) => item.trim());
        const pair = parts.find((item) => item.startsWith(`${name}=`));
        return pair ? decodeURIComponent(pair.split("=")[1]) : null;
    }

    async function api(path, options = {}) {
        const headers = new Headers(options.headers || {});
        const csrf = getCookie(csrfCookieName);
        if (csrf) {
            headers.set("X-CSRF-Token", csrf);
        }
        if (options.body && !headers.has("Content-Type")) {
            headers.set("Content-Type", "application/json");
        }
        const response = await fetch(path, {
            credentials: "include",
            ...options,
            headers,
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            const detail = payload.detail || payload.message || "Ошибка запроса";
            throw new Error(detail);
        }
        return payload;
    }

    function setError(targetId, message) {
        const node = document.getElementById(targetId);
        if (node) {
            node.textContent = message || "";
        }
    }

    async function submitAuthForm(formId, endpoint) {
        const form = document.getElementById(formId);
        if (!form) {
            return;
        }

        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            setError("auth-error", "");

            const formData = new FormData(form);
            const payload = Object.fromEntries(formData.entries());

            try {
                await api(endpoint, {
                    method: "POST",
                    body: JSON.stringify(payload),
                });
                window.location.href = "/app";
            } catch (error) {
                setError("auth-error", error.message);
            }
        });
    }

    function appendMessage(message) {
        const container = document.getElementById("messages");
        if (!container) {
            return;
        }

        if (state.currentChatId !== message.chat_id) {
            return;
        }

        const article = document.createElement("article");
        article.className = "message";
        article.innerHTML = `
            <div class="meta">
                <strong>#${message.sender_id}</strong>
                <span>${message.status}</span>
            </div>
            <p>${message.text}</p>
            <button type="button" data-message-id="${message.id}">Прочитано</button>
        `;

        const button = article.querySelector("button");
        button.addEventListener("click", () => markRead(message.id));
        container.appendChild(article);
        container.scrollTop = container.scrollHeight;
    }

    function connectWebSocket() {
        if (!document.querySelector("main.app-layout")) {
            return;
        }

        const protocol = window.location.protocol === "https:" ? "wss" : "ws";
        state.ws = new WebSocket(`${protocol}://${window.location.host}/ws`);

        state.ws.onopen = () => {
            state.reconnectDelayMs = 1000;
            window.setInterval(() => {
                if (state.ws && state.ws.readyState === WebSocket.OPEN) {
                    state.ws.send(JSON.stringify({ type: "heartbeat" }));
                }
            }, 25000);
        };

        state.ws.onmessage = (event) => {
            const payload = JSON.parse(event.data);
            if (payload.type === "message:new") {
                appendMessage(payload.message);
            }
            if (payload.type === "call:ringing" || payload.type === "call:signal" || payload.type === "call:status") {
                if (window.MessgoCall && typeof window.MessgoCall.onEvent === "function") {
                    window.MessgoCall.onEvent(payload);
                }
            }
        };

        state.ws.onclose = () => {
            const delay = state.reconnectDelayMs;
            state.reconnectDelayMs = Math.min(state.reconnectDelayMs * 2, 15000);
            window.setTimeout(connectWebSocket, delay);
        };
    }

    async function loadMessages(chatId) {
        const target = document.getElementById("messages");
        if (!target) {
            return;
        }
        try {
            const messages = await api(`/api/chats/${chatId}/messages?limit=100&offset=0`);
            target.innerHTML = "";
            messages.forEach((message) => appendMessage(message));
        } catch (error) {
            setError("app-error", error.message);
        }
    }

    function selectChat(chatId, title) {
        state.currentChatId = chatId;
        state.currentChatTitle = title || `Чат #${chatId}`;
        const titleNode = document.getElementById("chat-title");
        const sendButton = document.getElementById("send-message-button");
        const callButton = document.getElementById("start-call-button");
        if (titleNode) {
            titleNode.textContent = state.currentChatTitle;
        }
        if (sendButton) {
            sendButton.disabled = false;
        }
        if (callButton) {
            callButton.disabled = false;
        }
        loadMessages(chatId);
    }

    async function sendMessage(event) {
        event.preventDefault();
        setError("app-error", "");

        if (!state.currentChatId) {
            setError("app-error", "Сначала выберите чат");
            return;
        }

        const input = document.getElementById("message-text");
        if (!input) {
            return;
        }

        const text = input.value.trim();
        if (!text) {
            return;
        }

        try {
            const message = await api(`/api/chats/${state.currentChatId}/messages`, {
                method: "POST",
                body: JSON.stringify({ text }),
            });
            appendMessage(message);
            input.value = "";
        } catch (error) {
            setError("app-error", error.message);
        }
    }

    async function markRead(messageId) {
        try {
            await api(`/api/messages/${messageId}/read`, {
                method: "POST",
            });
        } catch (error) {
            setError("app-error", error.message);
        }
    }

    async function createDirect(event) {
        event.preventDefault();
        const formData = new FormData(event.target);
        const peerId = Number(formData.get("peer_id"));
        try {
            await api("/api/chats", {
                method: "POST",
                body: JSON.stringify({
                    type: "direct",
                    peer_id: peerId,
                }),
            });
            document.body.dispatchEvent(new Event("refresh-chats"));
        } catch (error) {
            setError("app-error", error.message);
        }
    }

    async function createGroup(event) {
        event.preventDefault();
        const formData = new FormData(event.target);
        const title = String(formData.get("title") || "").trim();
        const memberIdsRaw = String(formData.get("member_ids") || "").trim();
        const memberIds = memberIdsRaw
            ? memberIdsRaw.split(",").map((item) => Number(item.trim())).filter((item) => Number.isInteger(item) && item > 0)
            : [];

        try {
            await api("/api/chats", {
                method: "POST",
                body: JSON.stringify({
                    type: "group",
                    title,
                    member_ids: memberIds,
                }),
            });
            document.body.dispatchEvent(new Event("refresh-chats"));
        } catch (error) {
            setError("app-error", error.message);
        }
    }

    async function logout() {
        try {
            await api("/api/auth/logout", { method: "POST" });
        } finally {
            window.location.href = "/";
        }
    }

    function initAppPage() {
        const form = document.getElementById("send-message-form");
        const directForm = document.getElementById("create-direct-form");
        const groupForm = document.getElementById("create-group-form");
        const logoutButton = document.getElementById("logout-button");
        if (form) {
            form.addEventListener("submit", sendMessage);
        }
        if (directForm) {
            directForm.addEventListener("submit", createDirect);
        }
        if (groupForm) {
            groupForm.addEventListener("submit", createGroup);
        }
        if (logoutButton) {
            logoutButton.addEventListener("click", logout);
        }
        connectWebSocket();
    }

    window.Messgo = {
        selectChat,
        markRead,
        getCurrentChatId: () => state.currentChatId,
        api,
    };

    submitAuthForm("login-form", "/api/auth/login");
    submitAuthForm("register-form", "/api/auth/register");
    initAppPage();

    if ("serviceWorker" in navigator) {
        navigator.serviceWorker.register("/static/js/sw.js").catch(() => null);
    }
})();
