(() => {
    const state = {
        callId: null,
        peerConnection: null,
        localStream: null,
        remoteUserId: null,
        isMuted: false,
    };

    const rtcConfig = {
        iceServers: [
            { urls: ["stun:stun.l.google.com:19302"] },
        ],
    };

    async function ensureLocalAudio() {
        if (state.localStream) {
            return state.localStream;
        }
        state.localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
        return state.localStream;
    }

    async function ensurePeerConnection() {
        if (state.peerConnection) {
            return state.peerConnection;
        }

        const connection = new RTCPeerConnection(rtcConfig);
        connection.onicecandidate = async (event) => {
            if (!event.candidate || !state.callId || !state.remoteUserId) {
                return;
            }
            await window.Messgo.api("/api/calls/signal", {
                method: "POST",
                body: JSON.stringify({
                    call_id: state.callId,
                    to_user_id: state.remoteUserId,
                    type: "ice-candidate",
                    payload: JSON.stringify(event.candidate),
                }),
            });
        };

        const localStream = await ensureLocalAudio();
        localStream.getTracks().forEach((track) => connection.addTrack(track, localStream));

        state.peerConnection = connection;
        return connection;
    }

    async function startCall() {
        const chatId = window.Messgo.getCurrentChatId();
        if (!chatId) {
            return;
        }

        const toUserRaw = window.prompt("Введите ID пользователя для звонка");
        const toUserId = Number(toUserRaw);
        if (!Number.isInteger(toUserId) || toUserId <= 0) {
            return;
        }

        const response = await window.Messgo.api("/api/calls/start", {
            method: "POST",
            body: JSON.stringify({
                chat_id: chatId,
                to_user_id: toUserId,
            }),
        });

        state.callId = response.call_id;
        state.remoteUserId = toUserId;

        const connection = await ensurePeerConnection();
        const offer = await connection.createOffer({ offerToReceiveAudio: true, offerToReceiveVideo: false });
        await connection.setLocalDescription(offer);

        await window.Messgo.api("/api/calls/signal", {
            method: "POST",
            body: JSON.stringify({
                call_id: state.callId,
                to_user_id: toUserId,
                type: "offer",
                payload: JSON.stringify(offer),
            }),
        });

        setCallButtons(true);
    }

    function setCallButtons(active) {
        const muteButton = document.getElementById("mute-button");
        const hangupButton = document.getElementById("hangup-button");
        if (muteButton) {
            muteButton.disabled = !active;
        }
        if (hangupButton) {
            hangupButton.disabled = !active;
        }
    }

    async function mute() {
        if (!state.localStream) {
            return;
        }
        state.isMuted = !state.isMuted;
        state.localStream.getAudioTracks().forEach((track) => {
            track.enabled = !state.isMuted;
        });
    }

    async function hangup() {
        if (!state.callId) {
            return;
        }
        await window.Messgo.api(`/api/calls/${state.callId}/status`, {
            method: "POST",
            body: JSON.stringify({ status: "ended" }),
        });

        if (state.peerConnection) {
            state.peerConnection.close();
            state.peerConnection = null;
        }
        if (state.localStream) {
            state.localStream.getTracks().forEach((track) => track.stop());
            state.localStream = null;
        }
        state.callId = null;
        state.remoteUserId = null;
        setCallButtons(false);
    }

    async function onEvent(event) {
        if (event.type === "call:ringing") {
            const accept = window.confirm(`Входящий звонок от #${event.from_user_id}. Ответить?`);
            state.callId = event.call_id;
            state.remoteUserId = event.from_user_id;
            if (!accept) {
                await window.Messgo.api(`/api/calls/${state.callId}/status`, {
                    method: "POST",
                    body: JSON.stringify({ status: "declined" }),
                });
                state.callId = null;
                state.remoteUserId = null;
                return;
            }
            await window.Messgo.api(`/api/calls/${state.callId}/status`, {
                method: "POST",
                body: JSON.stringify({ status: "accepted" }),
            });
            await ensurePeerConnection();
            setCallButtons(true);
            return;
        }

        if (event.type === "call:signal") {
            const connection = await ensurePeerConnection();
            if (event.signal_type === "offer") {
                await connection.setRemoteDescription(JSON.parse(event.payload));
                const answer = await connection.createAnswer();
                await connection.setLocalDescription(answer);
                await window.Messgo.api("/api/calls/signal", {
                    method: "POST",
                    body: JSON.stringify({
                        call_id: event.call_id,
                        to_user_id: event.from_user_id,
                        type: "answer",
                        payload: JSON.stringify(answer),
                    }),
                });
            } else if (event.signal_type === "answer") {
                await connection.setRemoteDescription(JSON.parse(event.payload));
            } else if (event.signal_type === "ice-candidate") {
                await connection.addIceCandidate(JSON.parse(event.payload));
            }
            return;
        }

        if (event.type === "call:status" && ["ended", "declined", "missed"].includes(event.status)) {
            await hangup();
        }
    }

    function init() {
        const startButton = document.getElementById("start-call-button");
        const muteButton = document.getElementById("mute-button");
        const hangupButton = document.getElementById("hangup-button");

        if (startButton) {
            startButton.addEventListener("click", () => {
                startCall().catch((error) => {
                    const node = document.getElementById("app-error");
                    if (node) {
                        node.textContent = error.message;
                    }
                });
            });
        }
        if (muteButton) {
            muteButton.addEventListener("click", () => mute().catch(() => null));
        }
        if (hangupButton) {
            hangupButton.addEventListener("click", () => hangup().catch(() => null));
        }
    }

    window.MessgoCall = { onEvent };
    init();
})();
