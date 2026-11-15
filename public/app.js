const API_URL = "/api/generate";
const HEALTH_URL = "/api/health";
const MAX_MESSAGES = 50;

// 2. DOM-Elemente holen
const chatForm = document.getElementById("chat-form");
const userInput = document.getElementById("user-input");
const sendButton = document.getElementById("send-btn");
const chatMessages = document.getElementById("chat-messages");
const statusBadge = document.getElementById("status-badge");

function setStatus(online, label) {
  statusBadge.classList.toggle("online", online);
  const dot = document.createElement("span");
  dot.className = "status-dot";
  statusBadge.replaceChildren(dot, document.createTextNode(" " + label));
}

async function checkBackendHealth() {
  try {
    const response = await fetch(HEALTH_URL, { cache: "no-store" });
    setStatus(response.ok, response.ok ? "Backend Online" : "Backend Offline");
  } catch {
    setStatus(false, "Server offline");
  }
}

checkBackendHealth();

function addMessage(text, sender) {
  const messageDiv = document.createElement("div");
  messageDiv.className = "message " + sender + "-message";

  const bubbleDiv = document.createElement("div");
  bubbleDiv.className = "bubble";
  bubbleDiv.textContent = text;

  const timeSpan = document.createElement("span");
  timeSpan.className = "timestamp";
  timeSpan.textContent = sender === "user" ? "You" : "Lain";

  messageDiv.appendChild(bubbleDiv);
  messageDiv.appendChild(timeSpan);

  chatMessages.appendChild(messageDiv);
  while (chatMessages.querySelectorAll(".message").length > MAX_MESSAGES) {
    chatMessages.removeChild(chatMessages.firstElementChild);
  }
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return bubbleDiv;
}

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const promptText = userInput.value.trim();
  if (!promptText) return;

  userInput.value = "";
  sendButton.disabled = true;
  let thinkingBubble;

  try {
    addMessage(promptText, "user");
    thinkingBubble = addMessage("Transmitting through the Wired...", "bot");
    const response = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: promptText, max_tokens: 15 }),
      signal: AbortSignal.timeout(20000),
    });

    if (!response.ok) {
      throw new Error(`Server antwortet mit Status: ${response.status}`);
    }

    const data = await response.json();
    if (typeof data.completion !== "string") throw new Error("Invalid response");
    thinkingBubble.textContent = data.completion;
  } catch {
    if (thinkingBubble) {
      thinkingBubble.textContent = "Die Verbindung zum Modell ist gerade nicht verfügbar. Bitte versuche es erneut.";
    }
    checkBackendHealth();
  } finally {
    sendButton.disabled = false;
    userInput.focus();
  }
});
