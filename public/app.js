const API_URL = "/api/generate";
const HEALTH_URL = "/api/health";

// 2. DOM-Elemente holen
const chatForm = document.getElementById("chat-form");
const userInput = document.getElementById("user-input");
const sendButton = document.getElementById("send-btn");
const chatMessages = document.getElementById("chat-messages");
const statusBadge = document.getElementById("status-badge");

async function checkBackendHealth() {
  try {
    const response = await fetch(HEALTH_URL, { cache: "no-store" });
    if (response.ok) {
      statusBadge.classList.add("online");
      statusBadge.innerHTML = '<span class="status-dot"></span> Backend Online';
    } else {
      statusBadge.classList.remove("online");
      statusBadge.innerHTML = '<span class="status-dot"></span> Backend Offline';
    }
  } catch {
    statusBadge.classList.remove("online");
    statusBadge.innerHTML = '<span class="status-dot"></span> Server offline';
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
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return bubbleDiv;
}

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const promptText = userInput.value.trim();
  if (!promptText) return;

  userInput.value = "";
  sendButton.disabled = true;

  addMessage(promptText, "user");

  const thinkingBubble = addMessage("Transmitting through the Wired...", "bot");

  try {
    const response = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: promptText, max_tokens: 15 })
    });

    if (!response.ok) {
      throw new Error(`Server antwortet mit Status: ${response.status}`);
    }

    const data = await response.json();
    if (typeof data.completion !== "string") throw new Error("Invalid response");
    thinkingBubble.textContent = data.completion;

  } catch {
    thinkingBubble.textContent = "Die Verbindung zum Modell ist gerade nicht verfügbar. Bitte versuche es erneut.";
    checkBackendHealth();
  } finally {
    sendButton.disabled = false;
    userInput.focus();
  }
});
