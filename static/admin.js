const loginForm = document.querySelector("#admin-login-form");
const sessionCard = document.querySelector("#admin-session");
const sessionUsername = document.querySelector("#session-username");
const filtersForm = document.querySelector("#filters-form");
const statusNode = document.querySelector("#admin-status");
const requestList = document.querySelector("#request-list");
const emptyNode = document.querySelector("#admin-empty");
const reviewAdminList = document.querySelector("#review-admin-list");
const reviewsEmptyNode = document.querySelector("#reviews-empty");
const logoutButton = document.querySelector("#logout-button");
const changeUserButton = document.querySelector("#change-user-button");
const refreshButton = document.querySelector("#refresh-button");
const refreshReviewsButton = document.querySelector("#refresh-reviews-button");
const resetFiltersButton = document.querySelector("#reset-filters-button");
const taskTypeFilter = document.querySelector("#task-type-filter");
const reviewStatusFilter = document.querySelector("#review-status-filter");
const counterNode = document.querySelector("#admin-counter");

function setAdminStatus(message, isError = false) {
  if (!statusNode) {
    return;
  }
  statusNode.textContent = message;
  statusNode.classList.toggle("is-error", isError);
}

function updateCounter(count) {
  if (!counterNode) {
    return;
  }
  const suffix = count === 1 ? "заявка" : count >= 2 && count <= 4 ? "заявки" : "заявок";
  counterNode.textContent = `${count} ${suffix}`;
}

function getStoredAuth() {
  return window.localStorage.getItem("adminAuth") || "";
}

function storeAuth(username, password) {
  const token = btoa(`${username}:${password}`);
  window.localStorage.setItem("adminAuth", token);
  window.localStorage.setItem("adminUser", username);
}

function clearAuth() {
  window.localStorage.removeItem("adminAuth");
  window.localStorage.removeItem("adminUser");
}

function getStoredUser() {
  return window.localStorage.getItem("adminUser") || "";
}

function setAuthorizedState(isAuthorized) {
  document.documentElement.classList.toggle("admin-authenticated", isAuthorized);
  if (loginForm) {
    loginForm.classList.toggle("is-hidden", isAuthorized);
  }
  if (sessionCard) {
    sessionCard.classList.toggle("is-hidden", !isAuthorized);
  }
  if (sessionUsername) {
    sessionUsername.textContent = getStoredUser() || "admin";
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function getFilterParams() {
  if (!filtersForm) {
    return new URLSearchParams();
  }
  const params = new URLSearchParams();
  const formData = new FormData(filtersForm);
  for (const [key, rawValue] of formData.entries()) {
    const value = String(rawValue).trim();
    if (value) {
      params.set(key, value);
    }
  }
  return params;
}

function collectTaskTypes(items) {
  if (!taskTypeFilter) {
    return;
  }
  const existingValue = taskTypeFilter.value;
  const uniqueTypes = [...new Set(items.map((item) => String(item.taskType || "").trim()).filter(Boolean))].sort((a, b) => a.localeCompare(b, "ru"));
  taskTypeFilter.innerHTML = '<option value="">Все типы</option>';
  uniqueTypes.forEach((type) => {
    const option = document.createElement("option");
    option.value = type;
    option.textContent = type;
    taskTypeFilter.appendChild(option);
  });
  taskTypeFilter.value = uniqueTypes.includes(existingValue) ? existingValue : "";
}

function renderRequests(items) {
  if (!requestList || !emptyNode) {
    return;
  }
  requestList.innerHTML = "";
  updateCounter(items.length);
  if (!items.length) {
    emptyNode.hidden = false;
    emptyNode.textContent = getStoredAuth()
      ? "По текущим фильтрам ничего не найдено."
      : "Войдите, чтобы увидеть заявки.";
    return;
  }
  emptyNode.hidden = true;
  items.forEach((item) => {
    const card = document.createElement("article");
    card.className = "request-card";
    card.innerHTML = `
      <div class="request-card-head">
        <div>
          <strong>Заявка #${escapeHtml(item.id)}</strong>
          <span>${escapeHtml(formatDate(item.createdAt))}</span>
        </div>
        <button class="button button-danger request-delete" type="button" data-request-id="${escapeHtml(item.id)}">Удалить</button>
      </div>
      <div class="request-grid">
        <p><span>Имя</span>${escapeHtml(item.name)}</p>
        <p><span>Контакт</span>${escapeHtml(item.contact)}</p>
        <p><span>Тип работы</span>${escapeHtml(item.taskType)}</p>
        <p><span>Дедлайн</span>${escapeHtml(item.deadline)}</p>
      </div>
      <div class="request-details">
        <span>Описание</span>
        <p>${escapeHtml(item.details).replaceAll("\n", "<br>")}</p>
      </div>
    `;
    requestList.appendChild(card);
  });
}

function renderAdminReviews(items) {
  if (!reviewAdminList || !reviewsEmptyNode) {
    return;
  }
  reviewAdminList.innerHTML = "";
  if (!items.length) {
    reviewsEmptyNode.hidden = false;
    reviewsEmptyNode.textContent = getStoredAuth()
      ? "По текущему фильтру отзывов ничего не найдено."
      : "Войдите, чтобы увидеть отзывы.";
    return;
  }
  reviewsEmptyNode.hidden = true;
  items.forEach((item) => {
    const actions = [];
    actions.push(`<button class="button button-secondary review-save" type="button" data-review-id="${escapeHtml(item.id)}">Сохранить</button>`);
    if (item.status !== "approved") {
      actions.push(`<button class="button button-primary review-approve" type="button" data-review-id="${escapeHtml(item.id)}">Одобрить</button>`);
    }
    if (item.status !== "rejected") {
      actions.push(`<button class="button button-secondary review-reject" type="button" data-review-id="${escapeHtml(item.id)}">Отклонить</button>`);
    }
    actions.push(`<button class="button button-danger review-delete" type="button" data-review-id="${escapeHtml(item.id)}">Удалить</button>`);

    const card = document.createElement("article");
    card.className = "request-card";
    card.dataset.reviewId = String(item.id);
    card.innerHTML = `
      <div class="request-card-head">
        <div>
          <strong>Отзыв #${escapeHtml(item.id)}</strong>
          <span>${escapeHtml(formatDate(item.createdAt))}</span>
        </div>
        <span class="review-status review-status-${escapeHtml(item.status)}">${escapeHtml(item.status)}</span>
      </div>
      <div class="request-grid">
        <label class="review-edit-field">
          <span>Имя</span>
          <input class="review-edit-input" type="text" name="name" value="${escapeHtml(item.name)}">
        </label>
        <label class="review-edit-field">
          <span>Подпись</span>
          <input class="review-edit-input" type="text" name="role" value="${escapeHtml(item.role)}">
        </label>
      </div>
      <label class="request-details review-edit-field">
        <span>Текст</span>
        <textarea class="review-edit-textarea" name="text" rows="5">${escapeHtml(item.text)}</textarea>
      </label>
      <div class="admin-actions review-actions">${actions.join("")}</div>
    `;
    reviewAdminList.appendChild(card);
  });
}

async function fetchAdminJson(url, options = {}) {
  const auth = getStoredAuth();
  if (!auth) {
    throw new Error("Сначала выполните вход.");
  }
  const response = await fetch(url, {
    ...options,
    headers: {
      ...(options.headers || {}),
      Authorization: `Basic ${auth}`,
    },
  });
  const result = await response.json();
  if (!response.ok) {
    throw new Error(result.message || "Не удалось выполнить запрос.");
  }
  return result;
}

async function loadRequests() {
  const auth = getStoredAuth();
  if (!auth) {
    setAuthorizedState(false);
    renderRequests([]);
    setAdminStatus("Введите логин и пароль администратора.");
    return;
  }
  setAuthorizedState(true);
  setAdminStatus("Загружаю заявки...");
  try {
    const params = getFilterParams();
    const suffix = params.toString() ? `?${params.toString()}` : "";
    const result = await fetchAdminJson(`/api/requests${suffix}`);
    renderRequests(result.items || []);
    collectTaskTypes(result.items || []);
    setAdminStatus(`Заявки загружены: ${result.items.length}.`);
  } catch (error) {
    renderRequests([]);
    clearAuth();
    setAuthorizedState(false);
    setAdminStatus(error instanceof Error ? error.message : "Ошибка соединения.", true);
  }
}

async function loadAdminReviews() {
  if (!getStoredAuth()) {
    renderAdminReviews([]);
    return;
  }
  try {
    const params = new URLSearchParams();
    if (reviewStatusFilter && reviewStatusFilter.value) {
      params.set("status", reviewStatusFilter.value);
    }
    const suffix = params.toString() ? `?${params.toString()}` : "";
    const result = await fetchAdminJson(`/api/admin/reviews${suffix}`);
    renderAdminReviews(result.items || []);
  } catch (error) {
    renderAdminReviews([]);
    setAdminStatus(error instanceof Error ? error.message : "Ошибка загрузки отзывов.", true);
  }
}

async function deleteRequest(requestId) {
  const confirmed = window.confirm(`Удалить заявку #${requestId}? Это действие нельзя отменить.`);
  if (!confirmed) {
    return;
  }
  setAdminStatus(`Удаляю заявку #${requestId}...`);
  try {
    const result = await fetchAdminJson(`/api/requests/${requestId}`, { method: "DELETE" });
    setAdminStatus(result.message);
    await loadRequests();
  } catch (error) {
    setAdminStatus(error instanceof Error ? error.message : "Ошибка соединения.", true);
  }
}

async function moderateReview(reviewId, action) {
  const label = action === "approve" ? "одобряю" : "отклоняю";
  setAdminStatus(`${label.charAt(0).toUpperCase() + label.slice(1)} отзыв #${reviewId}...`);
  try {
    const result = await fetchAdminJson(`/api/admin/reviews/${reviewId}/${action}`, { method: "POST" });
    setAdminStatus(result.message);
    await loadAdminReviews();
  } catch (error) {
    setAdminStatus(error instanceof Error ? error.message : "Ошибка соединения.", true);
  }
}

function getReviewPayload(card) {
  const nameInput = card.querySelector('input[name="name"]');
  const roleInput = card.querySelector('input[name="role"]');
  const textInput = card.querySelector('textarea[name="text"]');
  return {
    name: nameInput instanceof HTMLInputElement ? nameInput.value.trim() : "",
    role: roleInput instanceof HTMLInputElement ? roleInput.value.trim() : "",
    text: textInput instanceof HTMLTextAreaElement ? textInput.value.trim() : "",
  };
}

async function saveReview(reviewId, card) {
  setAdminStatus(`Сохраняю отзыв #${reviewId}...`);
  try {
    const payload = getReviewPayload(card);
    const result = await fetchAdminJson(`/api/admin/reviews/${reviewId}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    setAdminStatus(result.message);
    await loadAdminReviews();
  } catch (error) {
    setAdminStatus(error instanceof Error ? error.message : "Ошибка соединения.", true);
  }
}

async function deleteReview(reviewId) {
  const confirmed = window.confirm(`Удалить отзыв #${reviewId}? Это действие нельзя отменить.`);
  if (!confirmed) {
    return;
  }
  setAdminStatus(`Удаляю отзыв #${reviewId}...`);
  try {
    const result = await fetchAdminJson(`/api/admin/reviews/${reviewId}`, { method: "DELETE" });
    setAdminStatus(result.message);
    await loadAdminReviews();
  } catch (error) {
    setAdminStatus(error instanceof Error ? error.message : "Ошибка соединения.", true);
  }
}

if (loginForm) {
  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(loginForm);
    storeAuth(String(formData.get("username") || "").trim(), String(formData.get("password") || ""));
    await loadRequests();
    await loadAdminReviews();
  });
}

if (filtersForm) {
  filtersForm.addEventListener("submit", (event) => {
    event.preventDefault();
    loadRequests();
  });
}

if (resetFiltersButton && filtersForm) {
  resetFiltersButton.addEventListener("click", () => {
    filtersForm.reset();
    loadRequests();
  });
}

if (logoutButton) {
  logoutButton.addEventListener("click", () => {
    clearAuth();
    if (loginForm) {
      loginForm.reset();
    }
    setAuthorizedState(false);
    renderRequests([]);
    renderAdminReviews([]);
    setAdminStatus("Авторизация очищена.");
  });
}

if (changeUserButton) {
  changeUserButton.addEventListener("click", () => {
    clearAuth();
    setAuthorizedState(false);
    renderRequests([]);
    renderAdminReviews([]);
    setAdminStatus("Введите данные другого аккаунта.");
    if (loginForm) {
      loginForm.reset();
      const usernameInput = loginForm.querySelector('input[name="username"]');
      if (usernameInput instanceof HTMLInputElement) {
        usernameInput.focus();
      }
    }
  });
}

if (refreshButton) {
  refreshButton.addEventListener("click", () => {
    loadRequests();
  });
}

if (refreshReviewsButton) {
  refreshReviewsButton.addEventListener("click", () => {
    loadAdminReviews();
  });
}

if (reviewStatusFilter) {
  reviewStatusFilter.addEventListener("change", () => {
    loadAdminReviews();
  });
}

if (requestList) {
  requestList.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }
    const button = target.closest(".request-delete");
    if (!button) {
      return;
    }
    const requestId = button.getAttribute("data-request-id");
    if (requestId) {
      deleteRequest(requestId);
    }
  });
}

if (reviewAdminList) {
  reviewAdminList.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }
    const card = target.closest(".request-card");
    if (!(card instanceof HTMLElement)) {
      return;
    }
    const reviewId = card.dataset.reviewId || "";
    if (!reviewId) {
      return;
    }
    const saveButton = target.closest(".review-save");
    if (saveButton) {
      saveReview(reviewId, card);
      return;
    }
    const approveButton = target.closest(".review-approve");
    if (approveButton) {
      moderateReview(reviewId, "approve");
      return;
    }
    const rejectButton = target.closest(".review-reject");
    if (rejectButton) {
      moderateReview(reviewId, "reject");
      return;
    }
    const deleteButton = target.closest(".review-delete");
    if (deleteButton) {
      deleteReview(reviewId);
    }
  });
}

setAuthorizedState(Boolean(getStoredAuth()));
loadRequests();
loadAdminReviews();
