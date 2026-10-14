const API =
  import.meta.env.VITE_API_URL ||
  "http://127.0.0.1:8000/api";


async function request(path, options = {}) {
  const token = localStorage.getItem("careflow_token");

  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  // Add authentication token automatically
  if (token) {
    headers.Authorization = `Token ${token}`;
  }

  const response = await fetch(`${API}${path}`, {
    ...options,
    headers,
  });

  const text = await response.text();

  let data;

  try {
    data = text ? JSON.parse(text) : {};
  } catch (error) {
    console.error("API returned non-JSON response:", {
      url: `${API}${path}`,
      status: response.status,
      contentType: response.headers.get("content-type"),
      body: text.slice(0, 500),
    });

    throw new Error(
      `API returned HTML/non-JSON response (${response.status}).`
    );
  }

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;

    if (data.error) {
      message = data.error;
    } else if (data.detail) {
      message = data.detail;
    } else if (data.message) {
      message = data.message;
    } else if (data.errors) {
      message = JSON.stringify(data.errors);
    }

    throw new Error(message);
  }

  return data;
}


/* =========================
   AUTH
========================= */

export async function registerPatient(data) {
  return request("/auth/register/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}


export async function loginPatient(data) {
  return request("/auth/login/patient/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}


export async function loginDoctor(data) {
  return request("/auth/login/doctor/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}


/* =========================
   DOCTORS
========================= */

export async function getDoctors() {
  return request("/doctors/");
}


export async function getDoctorAvailability(doctorId) {
  return request(`/doctors/${doctorId}/availability/`);
}


/* =========================
   APPOINTMENTS
========================= */

export async function getAppointments() {
  return request("/appointments/");
}


export async function createAppointment(data) {
  return request("/appointments/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}


export async function cancelAppointment(id) {
  return request(`/appointments/${id}/`, {
    method: "PATCH",
    body: JSON.stringify({
      status: "CANCELLED",
    }),
  });
}


export async function rescheduleAppointment(id, data) {
  return request(`/appointments/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}


/* =========================
   CHAT
========================= */

export async function sendChat(message) {
  return request("/chat/", {
    method: "POST",
    body: JSON.stringify({
      message,
    }),
  });
}


/* =========================
   SAFETY
========================= */

export async function safetyCheck(message) {
  return request("/safety/check/", {
    method: "POST",
    body: JSON.stringify({
      message,
    }),
  });
}


/* =========================
   RAG
========================= */

export async function queryRAG(question) {
  return request("/rag/query/", {
    method: "POST",
    body: JSON.stringify({
      query: question,
    }),
  });
}


/* =========================
   REMINDERS
========================= */

export async function getReminders() {
  return request("/reminders/");
}


export async function createReminder(data) {
  return request("/reminders/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}


/* =========================
   AUTH HELPERS
========================= */

export function saveAuth(data) {
  if (!data) {
    return;
  }

  if (data.token) {
    localStorage.setItem(
      "careflow_token",
      data.token
    );
  }

  if (data.user) {
    localStorage.setItem(
      "careflow_user",
      JSON.stringify(data.user)
    );
  }
}


export function getStoredUser() {
  const user = localStorage.getItem(
    "careflow_user"
  );

  if (!user) {
    return null;
  }

  try {
    return JSON.parse(user);
  } catch (error) {
    console.error(
      "Invalid stored CareFlow user:",
      error
    );

    return null;
  }
}


export function getStoredToken() {
  return localStorage.getItem(
    "careflow_token"
  );
}


export function isLoggedIn() {
  return Boolean(
    localStorage.getItem("careflow_token")
  );
}


export function logout() {
  localStorage.removeItem(
    "careflow_token"
  );

  localStorage.removeItem(
    "careflow_user"
  );
}