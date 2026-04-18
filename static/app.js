const menuToggle = document.querySelector(".menu-toggle");
const siteNav = document.querySelector(".site-nav");
const navLinks = document.querySelectorAll(".site-nav a");
const faqItems = document.querySelectorAll(".faq-item");
const requestForm = document.querySelector("#request-form");
const requestStatusBox = document.querySelector("#form-status");
const reviewForm = document.querySelector("#review-form");
const reviewStatusBox = document.querySelector("#review-status");
const reviewsList = document.querySelector("#reviews-list");
const footerCopyButton = document.querySelector(".footer-copy-button");
const footerCopyStatus = document.querySelector("#footer-copy-status");
const loginForm = document.querySelector("#login-form");
const registerForm = document.querySelector("#register-form");
const resetRequestForm = document.querySelector("#reset-request-form");
const resetConfirmForm = document.querySelector("#reset-confirm-form");
const resetPanel = document.querySelector("#reset-panel");
const authStatus = document.querySelector("#auth-status");
const authTabs = document.querySelectorAll(".account-tab");
const authPopover = document.querySelector("#auth-popover");
const openLoginButton = document.querySelector("#open-login-button");
const openRegisterButton = document.querySelector("#open-register-button");
const openResetButtons = document.querySelectorAll('[data-auth-tab="reset"]');

if (menuToggle && siteNav) {
  menuToggle.addEventListener("click", () => {
    const expanded = menuToggle.getAttribute("aria-expanded") === "true";
    menuToggle.setAttribute("aria-expanded", String(!expanded));
    siteNav.classList.toggle("is-open", !expanded);
  });
}

navLinks.forEach((link) => {
  link.addEventListener("click", () => {
    menuToggle?.setAttribute("aria-expanded", "false");
    siteNav?.classList.remove("is-open");
  });
});

faqItems.forEach((item) => {
  const trigger = item.querySelector(".faq-question");
  trigger?.addEventListener("click", () => item.classList.toggle("is-open"));
});

function setStatus(node, message, isError = false) {
  if (!node) {
    return;
  }
  node.textContent = message;
  node.classList.toggle("is-error", isError);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function storeUserSession(token, user) {
  window.localStorage.setItem("userToken", token);
  window.localStorage.setItem("userProfile", JSON.stringify(user));
}

function switchAuthTab(tabName) {
  authTabs.forEach((tab) => tab.classList.toggle("is-active", tab.dataset.authTab === tabName));
  loginForm?.classList.toggle("is-hidden", tabName !== "login");
  registerForm?.classList.toggle("is-hidden", tabName !== "register");
  resetPanel?.classList.toggle("is-hidden", tabName !== "reset");
}

function openAuthPopover(tabName) {
  authPopover?.classList.remove("is-hidden");
  switchAuthTab(tabName);
}

async function handleJsonSubmit(form, url, statusNode, pendingMessage) {
  const formData = new FormData(form);
  const payload = Object.fromEntries(formData.entries());
  setStatus(statusNode, pendingMessage);
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await response.json();
  if (!response.ok) {
    const message = result.errors ? Object.values(result.errors)[0] : result.message || "Не удалось отправить форму.";
    throw new Error(message);
  }
  form.reset();
  setStatus(statusNode, result.message);
  return result;
}

function renderReviews(items) {
  if (!reviewsList) {
    return;
  }
  reviewsList.innerHTML = items.length
    ? items.map((item) => `
      <article class="review-card">
        <p>"${escapeHtml(item.text)}"</p>
        <span>${escapeHtml(item.name)}, ${escapeHtml(item.role)}</span>
      </article>
    `).join("")
    : `
      <article class="review-card">
        <p>Пока нет опубликованных отзывов. Ваш отзыв может стать первым после модерации.</p>
        <span>Ожидаю новые отклики</span>
      </article>
    `;
}

async function loadReviews() {
  try {
    const response = await fetch("/api/reviews");
    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.message || "Не удалось загрузить отзывы.");
    }
    renderReviews(result.items || []);
  } catch (error) {
    renderReviews([]);
  }
}

requestForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await handleJsonSubmit(requestForm, "/api/requests", requestStatusBox, "Отправляю заявку...");
  } catch (error) {
    setStatus(requestStatusBox, error instanceof Error ? error.message : "Ошибка соединения.", true);
  }
});

reviewForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await handleJsonSubmit(reviewForm, "/api/reviews", reviewStatusBox, "Отправляю отзыв...");
  } catch (error) {
    setStatus(reviewStatusBox, error instanceof Error ? error.message : "Ошибка соединения.", true);
  }
});

footerCopyButton?.addEventListener("click", async () => {
  const email = footerCopyButton.getAttribute("data-copy-email") || "";
  try {
    await navigator.clipboard.writeText(email);
    setStatus(footerCopyStatus, "Почта скопирована.");
  } catch (error) {
    setStatus(footerCopyStatus, "Не удалось скопировать почту.", true);
  }
});

openLoginButton?.addEventListener("click", () => openAuthPopover("login"));
openRegisterButton?.addEventListener("click", () => openAuthPopover("register"));
openResetButtons.forEach((button) => button.addEventListener("click", () => openAuthPopover("reset")));
authTabs.forEach((tab) => tab.addEventListener("click", () => switchAuthTab(tab.dataset.authTab || "login")));

document.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement) || !authPopover) {
    return;
  }
  if (target.closest(".header-auth")) {
    return;
  }
  authPopover.classList.add("is-hidden");
});

loginForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const result = await handleJsonSubmit(loginForm, "/api/auth/login", authStatus, "Выполняю вход...");
    storeUserSession(result.token, result.user);
    window.location.href = "/chat";
  } catch (error) {
    setStatus(authStatus, error instanceof Error ? error.message : "Неверный логин или пароль.", true);
  }
});

registerForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const result = await handleJsonSubmit(registerForm, "/api/auth/register", authStatus, "Создаю аккаунт...");
    storeUserSession(result.token, result.user);
    window.location.href = "/chat";
  } catch (error) {
    setStatus(authStatus, error instanceof Error ? error.message : "Ошибка регистрации.", true);
  }
});

resetRequestForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await handleJsonSubmit(resetRequestForm, "/api/auth/password-reset/request", authStatus, "Отправляю код...");
  } catch (error) {
    setStatus(authStatus, error instanceof Error ? error.message : "Ошибка отправки кода.", true);
  }
});

resetConfirmForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await handleJsonSubmit(resetConfirmForm, "/api/auth/password-reset/confirm", authStatus, "Меняю пароль...");
    switchAuthTab("login");
  } catch (error) {
    setStatus(authStatus, error instanceof Error ? error.message : "Ошибка восстановления.", true);
  }
});

switchAuthTab("login");
loadReviews();
