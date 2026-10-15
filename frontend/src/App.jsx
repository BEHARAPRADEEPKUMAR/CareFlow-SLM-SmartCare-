import React, { useEffect, useMemo, useRef, useState } from "react";

/* =========================================================
   CONFIGURATION
   ========================================================= */

const API_BASE =
  import.meta.env.VITE_API_BASE_URL ||
  "http://127.0.0.1:8000";

const TOKEN_KEY = "careflow_token";
const USER_KEY = "careflow_user";

/* =========================================================
   DOCTOR PHOTO METADATA
   Doctor names, departments, fees and experience are loaded
   from the public Django endpoint. This list is only used to
   preserve the existing portrait images where available.
   ========================================================= */

const DEMO_DOCTORS = [
  { id: 1, name: "Arjun Mehta", photo: `${import.meta.env.BASE_URL}doctors/dr-arjun-mehta.png`, department: "Cardiology" },
  { id: 2, name: "Priya Rao", photo: `${import.meta.env.BASE_URL}doctors/dr-priya-rao.png`, department: "Cardiology" },
  { id: 3, name: "Ananya Sharma", photo: `${import.meta.env.BASE_URL}doctors/dr-ananya-sharma.png`, department: "Dermatology" },
  { id: 4, name: "Vikram Singh", photo: `${import.meta.env.BASE_URL}doctors/dr-vikram-singh.png`, department: "Neurology" },
  { id: 5, name: "Rahul Verma", photo: `${import.meta.env.BASE_URL}doctors/dr-rahul-verma.png`, department: "Orthopedics" },
  { id: 6, name: "Kiran Reddy", photo: `${import.meta.env.BASE_URL}doctors/kiran-reddy.png`, department: "General Medicine" },
  { id: 7, name: "Sneha Sharma", photo: `${import.meta.env.BASE_URL}doctors/sneha-sharma.png`, department: "Pulmonology" },
  { id: 8, name: "Neha Patel", photo: `${import.meta.env.BASE_URL}doctors/neha-patel.png`, department: "Endocrinology" },
  { id: 9, name: "Aditya Rao", photo: `${import.meta.env.BASE_URL}doctors/aditya-rao.png`, department: "Gastroenterology / Hepatology" },
  { id: 10, name: "Meera Nair", photo: `${import.meta.env.BASE_URL}doctors/meera-nair.png`, department: "Infectious Disease" },
];

/* =========================================================
   HOSPITAL SERVICES
   ========================================================= */

const HOSPITAL_SERVICES = [
  {
    icon: "♥",
    title: "Cardiology",
    description:
      "Heart health consultations, follow-ups and appointment scheduling.",
  },
  {
    icon: "✦",
    title: "Dermatology",
    description:
      "Skin, hair and dermatology consultations with specialists.",
  },
  {
    icon: "◆",
    title: "Orthopedics",
    description:
      "Bone, joint and musculoskeletal consultations.",
  },
  {
    icon: "✚",
    title: "General Medicine",
    description:
      "Primary care consultations and general health support.",
  },
  {
    icon: "◉",
    title: "Appointment Management",
    description:
      "Book, view, reschedule and manage your appointments.",
  },
  {
    icon: "⌁",
    title: "Patient Communication",
    description:
      "AI-assisted reminders, hospital FAQs and patient communication.",
  },
];

/* =========================================================
   SPECIALIZATIONS
   ========================================================= */

const SPECIALIZATIONS = [
  {
    name: "Cardiology",
    description:
      "Heart and cardiovascular care",
    icon: "♥",
  },
  {
    name: "Dermatology",
    description:
      "Skin, hair and nail care",
    icon: "✦",
  },
  {
    name: "Orthopedics",
    description:
      "Bones, joints and mobility",
    icon: "◆",
  },
  {
    name: "General Medicine",
    description:
      "Primary and general healthcare",
    icon: "✚",
  },
  {
    name: "Neurology",
    description:
      "Brain, spine and nervous system care",
    icon: "◉",
  },
];

/* =========================================================
   DOCTOR DIRECTORY API
   ========================================================= */

function getDoctorPhoto(doctorLike) {
  const rawName =
    typeof doctorLike === "string"
      ? doctorLike
      : doctorLike?.doctor_name ||
        doctorLike?.name ||
        doctorLike?.doctor?.name ||
        doctorLike?.doctor?.full_name ||
        "";

  const normalizedName = String(rawName)
    .replace(/^Dr\\.?\\s*/i, "")
    .trim()
    .toLowerCase();

  const knownDoctor = DEMO_DOCTORS.find(
    (doctor) => doctor.name.toLowerCase() === normalizedName
  );

  if (typeof doctorLike === "object" && doctorLike) {
    return (
      doctorLike.doctor_photo ||
      doctorLike.doctor_image ||
      doctorLike.photo ||
      doctorLike.image ||
      doctorLike.doctor?.photo ||
      doctorLike.doctor?.image ||
      knownDoctor?.photo ||
      ""
    );
  }

  return knownDoctor?.photo || "";
}

function getDoctorInitials(doctorLike) {
  const rawName =
    typeof doctorLike === "string"
      ? doctorLike
      : doctorLike?.doctor_name ||
        doctorLike?.name ||
        doctorLike?.doctor?.name ||
        doctorLike?.doctor?.full_name ||
        "Doctor";

  return String(rawName)
    .replace(/^Dr\\.?\\s*/i, "")
    .trim()
    .split(/\\s+/)
    .filter(Boolean)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase() || "DR";
}

function normalizeDoctorFromApi(apiDoctor) {
  const name = String(apiDoctor?.name || "Doctor").trim();
  const department = String(
    apiDoctor?.department_name || apiDoctor?.department?.name || "General Medicine"
  ).trim();
  const photoRecord = DEMO_DOCTORS.find(
    (doctor) => doctor.name.toLowerCase() === name.toLowerCase()
  );
  const years = Number(apiDoctor?.experience_years);
  const fee = Number(apiDoctor?.consultation_fee);

  return {
    id: apiDoctor.id,
    name,
    photo: photoRecord?.photo || "",
    department,
    specialization: department,
    experience: Number.isFinite(years)
      ? `${years}+ years`
      : "Experience not provided",
    qualification: apiDoctor?.qualification || "Qualification not provided",
    availability: "Check appointment slots",
    fee: Number.isFinite(fee) ? fee : null,
  };
}

function useDoctors() {
  const [doctors, setDoctors] = useState([]);
  const [loadingDoctors, setLoadingDoctors] = useState(true);
  const [doctorsError, setDoctorsError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadDoctors() {
      setLoadingDoctors(true);
      setDoctorsError("");

      try {
        // This endpoint is public; do not require a patient login.
        const response = await fetch(`${API_BASE}/api/doctors/`);
        let data = null;

        try {
          data = await response.json();
        } catch {
          data = null;
        }

        if (!response.ok) {
          throw new Error(
            data?.detail || data?.message || `Could not load doctors (HTTP ${response.status}).`
          );
        }

        const rows = Array.isArray(data)
          ? data
          : Array.isArray(data?.results)
          ? data.results
          : [];

        if (!cancelled) {
          setDoctors(rows.map(normalizeDoctorFromApi));
        }
      } catch (error) {
        if (!cancelled) {
          setDoctorsError(
            error?.message || "Unable to load doctors. Please try again."
          );
          setDoctors([]);
        }
      } finally {
        if (!cancelled) setLoadingDoctors(false);
      }
    }

    loadDoctors();

    return () => {
      cancelled = true;
    };
  }, []);

  return { doctors, loadingDoctors, doctorsError };
}

/* =========================================================
   AUTH HELPERS
   ========================================================= */

function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

function getStoredUser() {
  try {
    const raw = localStorage.getItem(USER_KEY);

    if (!raw) {
      return null;
    }

    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function saveAuth(token, user) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

function readBloodGroup(user) {
  const value =
    user?.blood_group ||
    user?.bloodGroup ||
    user?.profile?.blood_group ||
    user?.profile?.bloodGroup ||
    user?.patient?.blood_group ||
    user?.patient_profile?.blood_group ||
    user?.patientProfile?.blood_group ||
    "";
  return String(value || "").trim();
}

async function loadUserProfile(user, fallbackBloodGroup = "") {
  let profileData = null;

  try {
    profileData = await apiRequest("/api/auth/me/");
  } catch {
    // Some deployments may not expose the profile endpoint.
    // Keep the authenticated user data rather than breaking login.
  }

  const profileUser =
    profileData?.user ||
    profileData?.data?.user ||
    profileData?.data ||
    profileData ||
    {};

  const bloodGroup =
    readBloodGroup(profileUser) ||
    readBloodGroup(profileData) ||
    readBloodGroup(user) ||
    fallbackBloodGroup;

  const mergedUser = {
    ...(user || {}),
    ...(profileUser || {}),
    ...(bloodGroup ? { blood_group: bloodGroup } : {}),
  };

  saveAuth(getToken(), mergedUser);
  return mergedUser;
}

function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

/* =========================================================
   API HELPER
   ========================================================= */

async function apiRequest(endpoint, options = {}) {
  const token = getToken();

  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  if (token) {
    headers.Authorization = `Token ${token}`;
  }

  const response = await fetch(
    `${API_BASE}${endpoint}`,
    {
      ...options,
      headers,
    }
  );

  let data = null;

  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    const error = new Error(
      extractErrorMessage({
        response: data,
        status: response.status,
      })
    );

    error.status = response.status;
    error.data = data;

    throw error;
  }

  return data;
}

/* =========================================================
   ERROR HELPERS
   ========================================================= */

function extractErrorMessage(error) {
  if (!error) {
    return "Something went wrong.";
  }

  if (typeof error === "string") {
    return error;
  }

  if (error.message && error.message !== "Something went wrong.") {
    return error.message;
  }

  const data =
    error.response ||
    error.data ||
    error;

  if (typeof data === "string") {
    return data;
  }

  if (data?.detail) {
    return String(data.detail);
  }

  if (data?.message) {
    return String(data.message);
  }

  if (data?.error) {
    return String(data.error);
  }

  if (data?.errors) {
    return flattenErrors(data.errors);
  }

  return "Something went wrong. Please try again.";
}

function flattenErrors(errors) {
  if (!errors) {
    return "Invalid request.";
  }

  if (typeof errors === "string") {
    return errors;
  }

  if (Array.isArray(errors)) {
    return errors.join(", ");
  }

  if (typeof errors === "object") {
    return Object.entries(errors)
      .map(([key, value]) => {
        const message = Array.isArray(value)
          ? value.join(", ")
          : typeof value === "object"
          ? JSON.stringify(value)
          : String(value);

        return `${key}: ${message}`;
      })
      .join(" | ");
  }

  return "Invalid request.";
}

/* =========================================================
   GENERAL HELPERS
   ========================================================= */

function getNestedValue(object, paths) {
  for (const path of paths) {
    const parts = path.split(".");
    let current = object;

    for (const part of parts) {
      if (
        current === null ||
        current === undefined
      ) {
        current = undefined;
        break;
      }

      current = current[part];
    }

    if (
      current !== undefined &&
      current !== null &&
      current !== ""
    ) {
      return current;
    }
  }

  return null;
}

function cleanAssistantText(text) {
  if (!text) {
    return "";
  }

  return String(text)
    .replace(/BOOK_APPOINTMENTSAFE/gi, "")
    .replace(/BOOK_APPOINTMENT/gi, "")
    .replace(/\bSAFE\b/gi, "")
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .replace(/[ \t]{2,}/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

/* =========================================================
   DATE HELPERS
   ========================================================= */

function padNumber(number) {
  return String(number).padStart(2, "0");
}

function localDateToISO(date) {
  return [
    date.getFullYear(),
    padNumber(date.getMonth() + 1),
    padNumber(date.getDate()),
  ].join("-");
}

function parseDateOnly(value) {
  if (!value) {
    return null;
  }

  const text = String(value).trim();

  const match = text.match(
    /^(\d{4})-(\d{1,2})-(\d{1,2})/
  );

  if (match) {
    const year = Number(match[1]);
    const month = Number(match[2]) - 1;
    const day = Number(match[3]);

    return new Date(
      year,
      month,
      day
    );
  }

  const parsed = new Date(text);

  if (Number.isNaN(parsed.getTime())) {
    return null;
  }

  return parsed;
}

function normalizeSlotDate(value) {
  if (!value) {
    return "";
  }

  const parsed = parseDateOnly(value);

  if (!parsed) {
    return String(value).slice(0, 10);
  }

  return localDateToISO(parsed);
}

function formatDate(value) {
  if (!value) {
    return "Date unavailable";
  }

  const parsed = parseDateOnly(value);

  if (!parsed) {
    return String(value);
  }

  return parsed.toLocaleDateString(
    "en-IN",
    {
      day: "2-digit",
      month: "short",
      year: "numeric",
    }
  );
}

function getTomorrowISO() {
  const tomorrow = new Date();

  tomorrow.setDate(
    tomorrow.getDate() + 1
  );

  return localDateToISO(tomorrow);
}

/* =========================================================
   TIME HELPERS
   ========================================================= */

function normalizeSlotTime(value) {
  if (!value) {
    return "";
  }

  let text = String(value)
    .trim()
    .toLowerCase()
    .replace(/\./g, "");

  const ampmMatch = text.match(
    /^(\d{1,2})(?::(\d{1,2}))?\s*(am|pm)$/
  );

  if (ampmMatch) {
    let hour = Number(ampmMatch[1]);
    const minute = Number(
      ampmMatch[2] || 0
    );

    const period = ampmMatch[3];

    if (period === "am" && hour === 12) {
      hour = 0;
    }

    if (period === "pm" && hour !== 12) {
      hour += 12;
    }

    return `${padNumber(hour)}:${padNumber(
      minute
    )}:00`;
  }

  const colonMatch = text.match(
    /^(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?$/
  );

  if (colonMatch) {
    return `${padNumber(
      Number(colonMatch[1])
    )}:${padNumber(
      Number(colonMatch[2])
    )}:${padNumber(
      Number(colonMatch[3] || 0)
    )}`;
  }

  return text;
}

function timeToMinutes(value) {
  if (!value) {
    return null;
  }

  const normalized =
    normalizeSlotTime(value);

  const match = normalized.match(
    /^(\d{2}):(\d{2})/
  );

  if (!match) {
    return null;
  }

  return (
    Number(match[1]) * 60 +
    Number(match[2])
  );
}

function formatTime(value) {
  if (!value) {
    return "Time unavailable";
  }

  const normalized =
    normalizeSlotTime(value);

  const minutes =
    timeToMinutes(normalized);

  if (minutes === null) {
    return String(value);
  }

  let hour = Math.floor(
    minutes / 60
  );

  const minute = minutes % 60;

  const period =
    hour >= 12 ? "PM" : "AM";

  hour = hour % 12;

  if (hour === 0) {
    hour = 12;
  }

  return `${hour}:${padNumber(
    minute
  )} ${period}`;
}

function parseRequestedTime(text) {
  if (!text) {
    return null;
  }

  const value = String(text)
    .toLowerCase()
    .replace(/\./g, "");

  const match = value.match(
    /(?:at|around|by|for)?\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b/
  );

  if (!match) {
    return null;
  }

  let hour = Number(match[1]);

  const minute = Number(
    match[2] || 0
  );

  const period = match[3];

  if (period === "am" && hour === 12) {
    hour = 0;
  }

  if (period === "pm" && hour !== 12) {
    hour += 12;
  }

  return (
    hour * 60 +
    minute
  );
}

/* =========================================================
   FEE HELPERS
   ========================================================= */

function slotFee(slot) {
  return getNestedValue(slot, [
    "consultation_fee",
    "fee",
    "doctor.consultation_fee",
    "doctor.fee",
  ]);
}

function formatFee(value) {
  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return "";
  }

  const number = Number(
    String(value).replace(/[^\d.]/g, "")
  );

  if (Number.isNaN(number)) {
    return String(value);
  }

  return `₹${number.toLocaleString(
    "en-IN"
  )}`;
}

/* =========================================================
   SLOT HELPERS
   ========================================================= */

function slotDoctorId(slot) {
  return getNestedValue(slot, [
    "doctor_id",
    "doctor.id",
    "doctor",
  ]);
}

function slotDoctorName(slot) {
  return (
    getNestedValue(slot, [
      "doctor_name",
      "doctor.name",
      "name",
    ]) || "Doctor"
  );
}

function slotDepartment(slot) {
  return (
    getNestedValue(slot, [
      "department",
      "department_name",
      "doctor.department.name",
      "specialization",
    ]) || "General Medicine"
  );
}

function slotDate(slot) {
  return getNestedValue(slot, [
    "date",
    "appointment_date",
    "appointmentDate",
  ]);
}

function slotTime(slot) {
  return getNestedValue(slot, [
    "time",
    "appointment_time",
    "appointmentTime",
  ]);
}

/* =========================================================
   CHAT RESPONSE HELPERS
   ========================================================= */

function extractChatText(data) {
  if (!data) {
    return "";
  }

  const candidates = [
    data.response,
    data.message,
    data.answer,
    data.reply,
    data.text,
    data.result?.response,
    data.result?.message,
    data.result?.answer,
    data.result?.reply,
    data.result?.text,
  ];

  for (const candidate of candidates) {
    if (
      typeof candidate === "string" &&
      candidate.trim()
    ) {
      return cleanAssistantText(
        candidate
      );
    }
  }

  return "";
}

/* =========================================================
   BOOKING OPTIONS EXTRACTION
   ========================================================= */

function getBookingOptions(data) {
  if (!data) {
    return [];
  }

  const candidates = [
    data.booking_options,
    data.bookingOptions,
    data.available_slots,
    data.availableSlots,
    data.options,
    data.slots,

    data.result?.booking_options,
    data.result?.bookingOptions,
    data.result?.available_slots,
    data.result?.availableSlots,
    data.result?.options,
    data.result?.slots,

    data.data?.booking_options,
    data.data?.bookingOptions,
    data.data?.available_slots,
    data.data?.availableSlots,
    data.data?.options,
    data.data?.slots,
  ];

  for (const candidate of candidates) {
    if (Array.isArray(candidate)) {
      return candidate;
    }
  }

  return [];
}

/* =========================================================
   RANK BOOKING OPTIONS
   ========================================================= */

function rankBookingOptions(
  options,
  requestedMinutes
) {
  if (!Array.isArray(options)) {
    return [];
  }

  const usable = options.filter(
    (option) =>
      slotDoctorId(option) &&
      slotDate(option) &&
      slotTime(option)
  );

  const sorted = [...usable].sort(
    (a, b) => {
      const aMinutes =
        timeToMinutes(
          slotTime(a)
        );

      const bMinutes =
        timeToMinutes(
          slotTime(b)
        );

      if (
        requestedMinutes !== null &&
        requestedMinutes !== undefined
      ) {
        const aDifference =
          aMinutes === null
            ? Number.MAX_SAFE_INTEGER
            : Math.abs(
                aMinutes -
                  requestedMinutes
              );

        const bDifference =
          bMinutes === null
            ? Number.MAX_SAFE_INTEGER
            : Math.abs(
                bMinutes -
                  requestedMinutes
              );

        if (
          aDifference !==
          bDifference
        ) {
          return (
            aDifference -
            bDifference
          );
        }
      }

      return (
        (aMinutes || 0) -
        (bMinutes || 0)
      );
    }
  );

  /*
   * Maximum 3 slots per doctor.
   * Maximum 6 slots total.
   */
  const doctorCounts = {};
  const result = [];

  for (const option of sorted) {
    const doctorId =
      String(
        slotDoctorId(option)
      );

    doctorCounts[doctorId] =
      doctorCounts[doctorId] || 0;

    if (
      doctorCounts[doctorId] >= 3
    ) {
      continue;
    }

    doctorCounts[doctorId] += 1;
    result.push(option);

    if (result.length >= 6) {
      break;
    }
  }

  return result;
}

/* =========================================================
   NORMALIZE APPOINTMENT RESPONSE
   ========================================================= */

function normalizeListResponse(data) {
  if (Array.isArray(data)) {
    return data;
  }

  if (Array.isArray(data?.results)) {
    return data.results;
  }

  if (Array.isArray(data?.data)) {
    return data.data;
  }

  if (Array.isArray(data?.appointments)) {
    return data.appointments;
  }

  return [];
}

/* =========================================================
   BUTTON
   ========================================================= */

function Button({
  children,
  onClick,
  type = "button",
  variant = "primary",
  disabled = false,
}) {
  return (
    <button
      type={type}
      className={`button button-${variant}`}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
}

/* =========================================================
   LOADING
   ========================================================= */

function LoadingBox({
  text = "Loading...",
}) {
  return (
    <div className="loading-box">
      <div className="loading-spinner"></div>
      <span>{text}</span>
    </div>
  );
}

/* =========================================================
   EMPTY STATE
   ========================================================= */

function EmptyState({
  icon = "◌",
  title,
  description,
}) {
  return (
    <div className="empty-state">
      <div className="empty-icon">
        {icon}
      </div>

      <h3>{title}</h3>

      <p>{description}</p>
    </div>
  );
}

/* =========================================================
   PUBLIC NAVBAR
   ========================================================= */

function PublicNavbar({
  onPatientLogin,
  onDoctorLogin,
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const closeMenu = () => setMenuOpen(false);

  return (
    <header className="public-navbar">

      <div className="brand">
        <div className="brand-mark">
          +
        </div>

        <div>
          <strong>
            SmartCare
          </strong>

          <span>
            HEALTHCARE INTELLIGENCE
          </span>
        </div>
      </div>

      <nav className={`public-nav${menuOpen ? " is-open" : ""}`}>

        <a href="#services" onClick={closeMenu}>
          Services
        </a>

        <a href="#specializations" onClick={closeMenu}>
          Specializations
        </a>

        <a href="#doctors" onClick={closeMenu}>
          Doctors
        </a>

        <button
          type="button"
          className="nav-menu-doctor"
          onClick={() => {
            closeMenu();
            onDoctorLogin();
          }}
        >
          Doctor Sign In
        </button>

      </nav>

      <div className="nav-actions">

        <button
          className="nav-login-button"
          onClick={onDoctorLogin}
        >
          Doctor Sign In
        </button>

        <button
          className="nav-primary-button"
          onClick={onPatientLogin}
        >
          Patient Sign In
        </button>

        <button
          type="button"
          className={`nav-menu-toggle${menuOpen ? " is-open" : ""}`}
          aria-label="Toggle menu"
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((open) => !open)}
        >
          <span />
          <span />
          <span />
        </button>

      </div>

    </header>
  );
}

/* =========================================================
   PUBLIC HOME
   ========================================================= */

function HomePage({
  onPatientLogin,
  onDoctorLogin,
  onRegister,
}) {
  const { doctors, loadingDoctors, doctorsError } = useDoctors();
  const displayedSpecializations = useMemo(() => {
    if (doctors.length === 0) return SPECIALIZATIONS;

    return [...new Set(doctors.map((doctor) => doctor.specialization).filter(Boolean))]
      .sort()
      .map((name) => {
        const existing = SPECIALIZATIONS.find((item) => item.name === name);
        return existing || {
          name,
          description: `Appointments with ${name.toLowerCase()} specialists`,
          icon: "✚",
        };
      });
  }, [doctors]);

  return (
    <div className="public-page">

      <PublicNavbar
        onPatientLogin={onPatientLogin}
        onDoctorLogin={onDoctorLogin}
      />

      {/* =====================================================
          HERO
          ===================================================== */}

      <section className="hero-section">

        <div className="hero-grid"></div>

        <div className="hero-content">

          <div className="hero-badge">
            <span></span>
            AI-POWERED HEALTHCARE COMMUNICATION
          </div>

          <h1>
            Healthcare made
            <br />

            <span>
              simple with AI.
            </span>
          </h1>

          <p>
            SmartCare combines intelligent appointment
            management, patient communication and
            healthcare workflows in one secure platform.
          </p>

          <div className="hero-buttons">

            <button
              className="hero-primary"
              onClick={onPatientLogin}
            >
              Patient Sign In
              <span>→</span>
            </button>

            <button
              className="hero-secondary"
              onClick={onRegister}
            >
              Create Patient Account
            </button>

          </div>

          <div className="hero-trust">

            <div>
              <strong>
                AI
              </strong>
              <span>
                Healthcare Assistant
              </span>
            </div>

            <div>
              <strong>
                24/7
              </strong>
              <span>
                Patient Communication
              </span>
            </div>

            <div>
              <strong>
                Secure
              </strong>
              <span>
                Appointment Workflow
              </span>
            </div>

          </div>

        </div>

        <div className="hero-visual">

          <div className="ai-orbit">

            <div className="orbit-ring orbit-one"></div>
            <div className="orbit-ring orbit-two"></div>

            <div className="hero-doctor-portrait-card">
              <img
                className="hero-doctor-portrait"
                src={`${import.meta.env.BASE_URL}doctors/dr-ananya-sharma.png`}
                alt="Confident female doctor with arms crossed"
                loading="eager"
              />
              <div className="hero-doctor-caption">
                <span className="hero-doctor-eyebrow">SMARTCARE AI</span>
                <strong>Your healthcare<br />communication assistant</strong>
                <span className="hero-doctor-online"><i /> AI system online</span>
              </div>
            </div>

          </div>

        </div>

      </section>

      {/* =====================================================
          SERVICES
          ===================================================== */}

      <section
        className="public-section"
        id="services"
      >

        <SectionHeading
          eyebrow="HOSPITAL SERVICES"
          title="Healthcare services designed around you."
          description="Access essential healthcare services and communication workflows through SmartCare."
        />

        <div className="services-grid">

          {HOSPITAL_SERVICES.map(
            (service) => (
              <div
                className="service-card"
                key={service.title}
              >

                <div className="service-icon">
                  {service.icon}
                </div>

                <h3>
                  {service.title}
                </h3>

                <p>
                  {service.description}
                </p>

                <span className="service-arrow">
                  →
                </span>

              </div>
            )
          )}

        </div>

      </section>

      {/* =====================================================
          SPECIALIZATIONS
          ===================================================== */}

      <section
        className="public-section section-alt"
        id="specializations"
      >

        <SectionHeading
          eyebrow="SPECIALIZATIONS"
          title="Find the right specialist."
          description="Connect with doctors across our core medical specializations."
        />

        <div className="specialization-grid">

          {displayedSpecializations.map(
            (item) => (
              <div
                className="specialization-card"
                key={item.name}
              >

                <div className="specialization-icon">
                  {item.icon}
                </div>

                <div>
                  <h3>
                    {item.name}
                  </h3>

                  <p>
                    {item.description}
                  </p>
                </div>

              </div>
            )
          )}

        </div>

      </section>

      {/* =====================================================
          DOCTORS
          ===================================================== */}

      <section
        className="public-section"
        id="doctors"
      >

        <SectionHeading
          eyebrow="OUR DOCTORS"
          title="Experienced healthcare professionals."
          description="Explore our doctors and their specializations."
        />

        <div className="doctor-grid">

          {loadingDoctors ? (
            <LoadingBox text="Loading doctors from the hospital directory..." />
          ) : doctorsError ? (
            <EmptyState
              icon="!"
              title="Doctors could not be loaded"
              description={`${doctorsError} Please check that the CareFlow backend is running.`}
            />
          ) : doctors.length === 0 ? (
            <EmptyState
              icon="◌"
              title="No active doctors available"
              description="Please check back later or contact the hospital."
            />
          ) : (
            doctors.map((doctor) => (
              <DoctorCard doctor={doctor} key={doctor.id} />
            ))
          )}

        </div>

      </section>

      {/* =====================================================
          CTA
          ===================================================== */}

      <section className="public-cta">

        <div>
          <span className="section-label">
            SMARTCARE AI
          </span>

          <h2>
            Ready to simplify
            <br />
            your healthcare journey?
          </h2>

          <p>
            Sign in to manage appointments and
            communicate with SmartCare AI.
          </p>
        </div>

        <button
          className="hero-primary"
          onClick={onPatientLogin}
        >
          Get Started
          <span>→</span>
        </button>

      </section>

      {/* =====================================================
          FOOTER
          ===================================================== */}

      <footer className="public-footer">

        <div className="brand">

          <div className="brand-mark">
            +
          </div>

          <div>
            <strong>
              SmartCare
            </strong>

            <span>
              HEALTHCARE INTELLIGENCE
            </span>
          </div>

        </div>

        <p>
          AI-powered appointment and patient
          communication workflows.
        </p>

      </footer>

    </div>
  );
}

/* =========================================================
   SECTION HEADING
   ========================================================= */

function SectionHeading({
  eyebrow,
  title,
  description,
}) {
  return (
    <div className="section-heading">

      <span className="section-label">
        {eyebrow}
      </span>

      <h2>
        {title}
      </h2>

      <p>
        {description}
      </p>

    </div>
  );
}

/* =========================================================
   DOCTOR CARD
   ========================================================= */

function DoctorCard({
  doctor,
}) {
  return (
    <div className="doctor-card">

      <div className={`doctor-avatar doctor-photo-avatar${doctor.photo ? "" : " doctor-photo-fallback"}`}>
        {doctor.photo ? (
          <img
            src={doctor.photo}
            alt={`Portrait of Dr. ${doctor.name}`}
            onError={(event) => {
              event.currentTarget.style.display = "none";
              event.currentTarget.parentElement.classList.add("doctor-photo-fallback");
              event.currentTarget.parentElement.textContent = doctor.name
                .split(" ")
                .map((part) => part[0])
                .join("")
                .slice(0, 2);
            }}
          />
        ) : (
          doctor.name.split(" ").map((part) => part[0]).join("").slice(0, 2)
        )}
      </div>

      <div className="doctor-card-content">

        <div className="doctor-specialty">
          {doctor.specialization}
        </div>

        <h3>
          Dr. {doctor.name}
        </h3>

        <p>
          {doctor.qualification}
        </p>

        <div className="doctor-meta">

          <span>
            {doctor.experience}
          </span>

          <span>
            {doctor.availability}
          </span>

        </div>

        <div className="doctor-fee">
          Consultation fee{" "}
          <strong>
            {doctor.fee === null || doctor.fee === undefined
              ? "Contact hospital"
              : formatFee(doctor.fee)}
          </strong>
        </div>

      </div>

    </div>
  );
}

/* =========================================================
   AUTH LAYOUT
   ========================================================= */

function AuthLayout({
  title,
  subtitle,
  children,
  onBack,
}) {
  return (
    <div className="auth-page">

      <div className="auth-background-grid"></div>

      <div className="auth-topbar">

        <div className="brand">

          <div className="brand-mark">
            +
          </div>

          <div>
            <strong>
              SmartCare
            </strong>

            <span>
              HEALTHCARE INTELLIGENCE
            </span>
          </div>

        </div>

        <button
          className="back-button"
          onClick={onBack}
        >
          ← Back to Hospital
        </button>

      </div>

      <div className="auth-container">

        <div className="auth-intro">

          <div className="hero-badge">
            <span></span>
            SMARTCARE HEALTHCARE
          </div>

          <h1>
            {title}
          </h1>

          <p>
            {subtitle}
          </p>

          <div className="auth-feature-list">

            <div>
              <span>✓</span>
              Secure patient communication
            </div>

            <div>
              <span>✓</span>
              AI-assisted appointment booking
            </div>

            <div>
              <span>✓</span>
              Easy appointment management
            </div>

          </div>

        </div>

        <div className="auth-card">
          {children}
        </div>

      </div>

    </div>
  );
}

/* =========================================================
   PATIENT LOGIN
   ========================================================= */

function PatientLoginPage({
  onLogin,
  onRegister,
  onBack,
}) {
  const [email, setEmail] =
    useState("");

  const [password, setPassword] =
    useState("");

  const [loading, setLoading] =
    useState(false);

  const [error, setError] =
    useState("");

  async function handleSubmit(event) {
    event.preventDefault();

    setError("");
    setLoading(true);

    try {
      const data =
        await apiRequest(
          "/api/auth/login/patient/",
          {
            method: "POST",
            body: JSON.stringify({
              email,
              password,
            }),
          }
        );

      saveAuth(
        data.token,
        data.user
      );

      const profileUser = await loadUserProfile(data.user);
      onLogin(profileUser);
    } catch (err) {
      setError(
        extractErrorMessage(err)
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthLayout
      title="Welcome back."
      subtitle="Sign in to manage your appointments and connect with SmartCare AI."
      onBack={onBack}
    >

      <div className="auth-card-header">

        <span className="section-label">
          PATIENT PORTAL
        </span>

        <h2>
          Patient Sign In
        </h2>

        <p>
          Access your SmartCare account.
        </p>

      </div>

      {error && (
        <div className="error-message">
          {error}
        </div>
      )}

      <form
        className="auth-form"
        onSubmit={handleSubmit}
      >

        <label>
          Email address

          <input
            type="email"
            value={email}
            onChange={(event) =>
              setEmail(
                event.target.value
              )
            }
            placeholder="you@example.com"
            required
          />
        </label>

        <label>
          Password

          <input
            type="password"
            value={password}
            onChange={(event) =>
              setPassword(
                event.target.value
              )
            }
            placeholder="Enter your password"
            required
          />
        </label>

        <button
          type="submit"
          className="auth-submit"
          disabled={loading}
        >
          {loading
            ? "Signing in..."
            : "Sign In"}
        </button>

      </form>

      <div className="auth-switch">

        <span>
          Don't have an account?
        </span>

        <button
          onClick={onRegister}
        >
          Create account
        </button>

      </div>

    </AuthLayout>
  );
}

/* =========================================================
   PATIENT REGISTER
   ========================================================= */

function PatientRegisterPage({
  onRegistered,
  onLogin,
  onBack,
}) {
  const [form, setForm] =
    useState({
      full_name: "",
      phone: "",
      email: "",
      password: "",
      confirm_password: "",
      blood_group: "",
    });

  const [loading, setLoading] =
    useState(false);

  const [error, setError] =
    useState("");

  function updateField(
    field,
    value
  ) {
    setForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  async function handleSubmit(event) {
    event.preventDefault();

    setError("");

    if (
      form.password !==
      form.confirm_password
    ) {
      setError(
        "Passwords do not match."
      );

      return;
    }

    setLoading(true);

    try {
      const data =
        await apiRequest(
          "/api/auth/register/",
          {
            method: "POST",
            body: JSON.stringify(form),
          }
        );

      const registeredUser = {
        ...(data.user || {}),
        blood_group:
          readBloodGroup(data.user) || form.blood_group,
      };

      saveAuth(
        data.token,
        registeredUser
      );

      const profileUser = await loadUserProfile(
        registeredUser,
        form.blood_group
      );
      onRegistered(profileUser);
    } catch (err) {
      setError(
        extractErrorMessage(err)
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthLayout
      title="Create your account."
      subtitle="Start managing your healthcare appointments with SmartCare."
      onBack={onBack}
    >

      <div className="auth-card-header">

        <span className="section-label">
          PATIENT PORTAL
        </span>

        <h2>
          Create Account
        </h2>

        <p>
          Register as a SmartCare patient.
        </p>

      </div>

      {error && (
        <div className="error-message">
          {error}
        </div>
      )}

      <form
        className="auth-form"
        onSubmit={handleSubmit}
      >

        <label>
          Full name

          <input
            type="text"
            value={form.full_name}
            onChange={(event) =>
              updateField(
                "full_name",
                event.target.value
              )
            }
            placeholder="Your full name"
            required
          />
        </label>

        <label>
          Mobile number

          <input
            type="tel"
            value={form.phone}
            onChange={(event) =>
              updateField(
                "phone",
                event.target.value
              )
            }
            placeholder="Your mobile number"
            required
          />
        </label>

        <label>
          Email address

          <input
            type="email"
            value={form.email}
            onChange={(event) =>
              updateField(
                "email",
                event.target.value
              )
            }
            placeholder="you@example.com"
            required
          />
        </label>

        <div className="blood-group-field">
          <label htmlFor="patient-blood-group" className="blood-group-label">
            <span className="blood-group-label-icon" aria-hidden="true">✚</span>
            <span>
              Blood group
              <small>Choose your blood type</small>
            </span>
            <span className="field-optional">PATIENT PROFILE</span>
          </label>

          <div className="blood-group-select-wrap">
            <span className="blood-group-select-icon" aria-hidden="true">🩸</span>
            <select
              id="patient-blood-group"
              className="blood-group-select"
              value={form.blood_group}
              onChange={(event) =>
                updateField(
                  "blood_group",
                  event.target.value
                )
              }
              required
            >
              <option value="">Select your blood group</option>
              <option value="A+">A positive (A+)</option>
              <option value="A-">A negative (A-)</option>
              <option value="B+">B positive (B+)</option>
              <option value="B-">B negative (B-)</option>
              <option value="AB+">AB positive (AB+)</option>
              <option value="AB-">AB negative (AB-)</option>
              <option value="O+">O positive (O+)</option>
              <option value="O-">O negative (O-)</option>
              <option value="Unknown">I don't know</option>
            </select>
            <span className="blood-group-chevron" aria-hidden="true">⌄</span>
          </div>

          <p className="blood-group-help">
            This helps keep your patient profile complete. Choose “I don't know”
            if you're unsure.
          </p>
        </div>

        <div className="form-two-columns">

          <label>
            Password

            <input
              type="password"
              value={form.password}
              onChange={(event) =>
                updateField(
                  "password",
                  event.target.value
                )
              }
              placeholder="Password"
              minLength={6}
              required
            />
          </label>

          <label>
            Confirm password

            <input
              type="password"
              value={
                form.confirm_password
              }
              onChange={(event) =>
                updateField(
                  "confirm_password",
                  event.target.value
                )
              }
              placeholder="Confirm"
              minLength={6}
              required
            />
          </label>

        </div>

        <button
          type="submit"
          className="auth-submit"
          disabled={loading}
        >
          {loading
            ? "Creating account..."
            : "Create Patient Account"}
        </button>

      </form>

      <div className="auth-switch">

        <span>
          Already have an account?
        </span>

        <button
          onClick={onLogin}
        >
          Sign in
        </button>

      </div>

    </AuthLayout>
  );
}

/* =========================================================
   DOCTOR LOGIN
   ========================================================= */

function DoctorLoginPage({
  onLogin,
  onBack,
}) {
  const [email, setEmail] =
    useState("");

  const [password, setPassword] =
    useState("");

  const [loading, setLoading] =
    useState(false);

  const [error, setError] =
    useState("");

  async function handleSubmit(event) {
    event.preventDefault();

    setError("");
    setLoading(true);

    try {
      const data =
        await apiRequest(
          "/api/auth/login/doctor/",
          {
            method: "POST",
            body: JSON.stringify({
              email,
              password,
            }),
          }
        );

      saveAuth(
        data.token,
        data.user
      );

      onLogin(data.user);
    } catch (err) {
      setError(
        extractErrorMessage(err)
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthLayout
      title="Doctor portal."
      subtitle="Access your appointments and patient information securely."
      onBack={onBack}
    >

      <div className="auth-card-header">

        <span className="section-label">
          CLINICIAN PORTAL
        </span>

        <h2>
          Doctor Sign In
        </h2>

        <p>
          Sign in to view your appointments.
        </p>

      </div>

      {error && (
        <div className="error-message">
          {error}
        </div>
      )}

      <form
        className="auth-form"
        onSubmit={handleSubmit}
      >

        <label>
          Doctor email

          <input
            type="email"
            value={email}
            onChange={(event) =>
              setEmail(
                event.target.value
              )
            }
            placeholder="doctor@careflow.com"
            required
          />
        </label>

        <label>
          Password

          <input
            type="password"
            value={password}
            onChange={(event) =>
              setPassword(
                event.target.value
              )
            }
            placeholder="Enter your password"
            required
          />
        </label>

        <button
          type="submit"
          className="auth-submit"
          disabled={loading}
        >
          {loading
            ? "Signing in..."
            : "Doctor Sign In"}
        </button>

      </form>

    </AuthLayout>
  );
}

/* =========================================================
   DASHBOARD TOPBAR
   ========================================================= */

function DashboardTopbar({
  user,
  onLogout,
}) {
  return (
    <header className="dashboard-topbar">

      <div className="brand">

        <div className="brand-mark">
          +
        </div>

        <div>
          <strong>
            SmartCare
          </strong>

          <span>
            HEALTHCARE INTELLIGENCE
          </span>
        </div>

      </div>

      <div
        className={`dashboard-user ${
          user?.role === "doctor"
            ? "dashboard-user-doctor"
            : "dashboard-user-patient"
        }`}
      >
        {user?.role === "doctor" ? (
          <>
            <div className="online-status">
              <span />
              AI Online
            </div>

            <div className="user-avatar user-avatar-photo">
              <img
                src={
                  DEMO_DOCTORS.find((doctor) =>
                    (user?.name || "")
                      .toLowerCase()
                      .includes(doctor.name.toLowerCase())
                  )?.photo || `${import.meta.env.BASE_URL}doctors/dr-arjun-mehta.png`
                }
                alt={`Dr. ${user?.name || "Doctor"}`}
                onError={(event) => {
                  event.currentTarget.style.display = "none";
                  event.currentTarget.parentElement.textContent = (
                    user?.name || "DR"
                  )
                    .split(" ")
                    .map((part) => part[0])
                    .join("")
                    .slice(0, 2);
                }}
              />
            </div>

            <div className="user-info">
              <strong>Dr. {user?.name}</strong>
              <span>DOCTOR</span>
            </div>

            <button className="logout-button" onClick={onLogout}>
              Logout
            </button>
          </>
        ) : (
          <>
            <div className="online-status">
              <span />
              AI Online
            </div>

            <div className="user-avatar patient-avatar">
              {(user?.name || "P")
                .split(" ")
                .map((part) => part[0])
                .join("")
                .slice(0, 2)
                .toUpperCase()}
            </div>

            <div className="patient-profile-stack">
              <strong className="patient-profile-name">
                {user?.name || "Patient"}
              </strong>

              <span className="patient-profile-role">
                PATIENT ACCOUNT
              </span>

              <div className="patient-blood-group-chip">
                <span aria-hidden="true">♥</span>
                <span>Blood group</span>
                <strong>{readBloodGroup(user) || "Not set"}</strong>
              </div>
            </div>

            <button className="logout-button patient-logout" onClick={onLogout}>
              <span aria-hidden="true">↗</span>
              Logout
            </button>
          </>
        )}
      </div>
    </header>
  );
}

/* =========================================================
   PATIENT DASHBOARD
   ========================================================= */

function PatientDashboard({
  user,
  onLogout,
}) {
  const [activeSection, setActiveSection] =
    useState("overview");

  const [appointments, setAppointments] =
    useState([]);

  const [loadingAppointments, setLoadingAppointments] =
    useState(true);

  async function loadAppointments() {
    setLoadingAppointments(true);

    try {
      const data =
        await apiRequest(
          "/api/appointments/"
        );

      setAppointments(
        normalizeListResponse(data)
      );
    } catch (error) {
      if (error.status === 401) {
        onLogout();
      }
    } finally {
      setLoadingAppointments(false);
    }
  }

  useEffect(() => {
    loadAppointments();
  }, []);

  return (
    <div className="dashboard-page">

      <DashboardTopbar
        user={user}
        onLogout={onLogout}
      />

      <div className="dashboard-shell">

        {/* =================================================
            SIDEBAR
            ================================================= */}

        <aside className="dashboard-sidebar">

          <div className="sidebar-welcome">
            <span>
              PATIENT PORTAL
            </span>

            <strong>
              Welcome,
              <br />
              {user?.name}
            </strong>
          </div>

          <nav className="dashboard-nav">

            <DashboardNavButton
              active={
                activeSection ===
                "overview"
              }
              onClick={() =>
                setActiveSection(
                  "overview"
                )
              }
              icon="⌂"
              label="Overview"
            />

            <DashboardNavButton
              active={
                activeSection ===
                "appointments"
              }
              onClick={() =>
                setActiveSection(
                  "appointments"
                )
              }
              icon="▣"
              label="Your Appointments"
            />

            <DashboardNavButton
              active={
                activeSection ===
                "ai"
              }
              onClick={() =>
                setActiveSection("ai")
              }
              icon="✦"
              label="AI Chatbot"
            />

            <DashboardNavButton
              active={
                activeSection ===
                "services"
              }
              onClick={() =>
                setActiveSection(
                  "services"
                )
              }
              icon="✚"
              label="Hospital Services"
            />

            <DashboardNavButton
              active={
                activeSection ===
                "doctors"
              }
              onClick={() =>
                setActiveSection(
                  "doctors"
                )
              }
              icon="◉"
              label="Doctors & Specializations"
            />

          </nav>

          <div className="sidebar-ai-card">

            <div className="sidebar-ai-icon">
              ✦
            </div>

            <strong>
              SmartCare AI
            </strong>

            <p>
              Ask me about appointments,
              doctors and hospital services.
            </p>

            <button
              onClick={() =>
                setActiveSection("ai")
              }
            >
              Open AI →
            </button>

          </div>

        </aside>

        {/* =================================================
            MAIN CONTENT
            ================================================= */}

        <main className="dashboard-main">

          {activeSection ===
            "overview" && (
            <PatientOverview
              user={user}
              appointments={
                appointments
              }
              loading={
                loadingAppointments
              }
              onOpenAI={() =>
                setActiveSection("ai")
              }
              onOpenAppointments={() =>
                setActiveSection(
                  "appointments"
                )
              }
            />
          )}

          {activeSection ===
            "appointments" && (
            <PatientAppointments
              appointments={
                appointments
              }
              loading={
                loadingAppointments
              }
              onRefresh={
                loadAppointments
              }
            />
          )}

          {activeSection ===
            "ai" && (
            <PatientAI
              user={user}
              appointments={appointments}
              appointmentsLoading={loadingAppointments}
              onAppointmentsUpdated={loadAppointments}
            />
          )}

          {activeSection ===
            "services" && (
            <PatientServices />
          )}

          {activeSection ===
            "doctors" && (
            <PatientDoctors />
          )}

        </main>

      </div>

    </div>
  );
}

/* =========================================================
   DASHBOARD NAV BUTTON
   ========================================================= */

function DashboardNavButton({
  active,
  onClick,
  icon,
  label,
}) {
  return (
    <button
      className={`dashboard-nav-button ${
        active ? "active" : ""
      }`}
      onClick={onClick}
    >
      <span className="dashboard-nav-icon">
        {icon}
      </span>

      <span>
        {label}
      </span>
    </button>
  );
}

/* =========================================================
   PATIENT OVERVIEW
   ========================================================= */

function isUpcomingAppointment(appointment) {
  const status = String(appointment?.status || "").toUpperCase();
  if (!["SCHEDULED", "CONFIRMED", "RESCHEDULED"].includes(status)) return false;

  const dateValue = appointment?.appointment_date || appointment?.date;
  const timeValue = appointment?.appointment_time || appointment?.time;
  if (!dateValue) return false;

  const dateText = String(dateValue).slice(0, 10);
  const timeText = String(timeValue || "23:59:59").slice(0, 8);
  const scheduled = new Date(`${dateText}T${timeText}`);
  if (Number.isNaN(scheduled.getTime())) return false;
  return scheduled.getTime() > Date.now();
}

function PatientOverview({
  user,
  appointments,
  loading,
  onOpenAI,
  onOpenAppointments,
}) {
  const upcoming = appointments
    .filter(isUpcomingAppointment)
    .sort((a, b) => {
      const aDate = `${a.appointment_date || a.date}T${a.appointment_time || a.time || "23:59:59"}`;
      const bDate = `${b.appointment_date || b.date}T${b.appointment_time || b.time || "23:59:59"}`;
      return new Date(aDate) - new Date(bDate);
    });

  const nextAppointment =
    upcoming[0];

  return (
    <>
      <div className="dashboard-heading">

        <div>
          <span className="section-label">
            PATIENT DASHBOARD
          </span>

          <h1>
            Hello,{" "}
            <span>
              {user?.name}
            </span>
          </h1>

          <p>
            Manage your healthcare journey
            with SmartCare.
          </p>
        </div>

        <button
          className="dashboard-ai-button"
          onClick={onOpenAI}
        >
          ✦ Ask SmartCare AI
        </button>

      </div>

      <div className="overview-stat-grid">

        <StatCard
          icon="▣"
          value={
            appointments.length
          }
          label="Total appointments"
        />

        <StatCard
          icon="◷"
          value={
            upcoming.length
          }
          label="Upcoming appointments"
        />

        <StatCard
          icon="✦"
          value="24/7"
          label="AI assistance"
        />

      </div>

      <div className="overview-grid">

        <div className="dashboard-card">

          <div className="card-header">

            <div>
              <span className="section-label">
                NEXT APPOINTMENT
              </span>

              <h2>
                Your upcoming visit
              </h2>
            </div>

            <button
              className="text-button"
              onClick={
                onOpenAppointments
              }
            >
              View all →
            </button>

          </div>

          {loading ? (
            <LoadingBox text="Loading appointments..." />
          ) : nextAppointment ? (
            <AppointmentPreview
              appointment={
                nextAppointment
              }
            />
          ) : (
            <EmptyState
              icon="▣"
              title="No upcoming appointments"
              description="Use SmartCare AI to find a doctor and book your next appointment."
            />
          )}

        </div>

        <div className="dashboard-card">

          <div className="card-header">

            <div>
              <span className="section-label">
                SMARTCARE AI
              </span>

              <h2>
                Need help?
              </h2>
            </div>

            <div className="small-ai-status">
              <span></span>
              Online
            </div>

          </div>

          <p className="card-description">
            Ask SmartCare AI to find a doctor,
            check appointment availability,
            answer hospital questions or help
            manage your appointments.
          </p>

          <button
            className="large-ai-button"
            onClick={onOpenAI}
          >
            <span>
              ✦
            </span>

            Open AI Assistant

            <strong>
              →
            </strong>
          </button>

        </div>

      </div>

      <section className="dashboard-card patient-health-analytics patient-analytics-redesign">
        <div className="card-header patient-analytics-header">
          <div>
            <span className="section-label">YOUR CARE ACTIVITY</span>
            <h2>Appointment activity</h2>
            <p className="card-description">A clear overview of your visits and appointment status.</p>
          </div>
          <span className="analytics-period"><span className="analytics-live-dot" /> LIVE OVERVIEW</span>
        </div>
        {(() => {
          const now = new Date();
          const months = Array.from({ length: 6 }, (_, index) => {
            const date = new Date(now.getFullYear(), now.getMonth() - 5 + index, 1);
            const records = appointments.filter((appointment) => {
              const parsed = parseDateOnly(appointment.appointment_date || appointment.date);
              return parsed && parsed.getFullYear() === date.getFullYear() && parsed.getMonth() === date.getMonth();
            });
            const status = (item) => String(item.status || "SCHEDULED").toUpperCase();
            return {
              label: date.toLocaleDateString("en-IN", { month: "short" }),
              total: records.length,
              scheduled: records.filter((a) => ["SCHEDULED", "CONFIRMED", "PENDING"].includes(status(a))).length,
              completed: records.filter((a) => status(a) === "COMPLETED").length,
              cancelled: records.filter((a) => status(a) === "CANCELLED").length,
              rescheduled: records.filter((a) => ["RESCHEDULED", "RESCHEDULE"].includes(status(a))).length,
            };
          });
          const status = (item) => String(item.status || "SCHEDULED").toUpperCase();
          const totalAppointments = appointments.length;
          const counts = [
            { label: "Completed", value: appointments.filter((a) => status(a) === "COMPLETED").length, color: "#38d9a9", className: "completed" },
            { label: "Scheduled", value: appointments.filter((a) => ["SCHEDULED", "CONFIRMED", "PENDING"].includes(status(a))).length, color: "#4f9cff", className: "scheduled" },
            { label: "Rescheduled", value: appointments.filter((a) => ["RESCHEDULED", "RESCHEDULE"].includes(status(a))).length, color: "#b58aff", className: "rescheduled" },
            { label: "Cancelled", value: appointments.filter((a) => status(a) === "CANCELLED").length, color: "#ff857a", className: "cancelled" },
          ];
          const maxMonthly = Math.max(1, ...months.map((m) => m.total));
          let accumulated = 0;
          const gradient = counts.filter((item) => item.value > 0).map((item) => {
            const from = accumulated / Math.max(1, totalAppointments) * 100;
            accumulated += item.value;
            return `${item.color} ${from}% ${accumulated / Math.max(1, totalAppointments) * 100}%`;
          }).join(", ");
          return (
            <div className="patient-analytics-grid patient-analytics-grid-new">
              <div className="patient-chart-panel patient-monthly-panel">
                <div className="analytics-panel-heading">
                  <div><span className="analytics-icon-bubble">↗</span><h3>Monthly trend</h3></div>
                  <span>Last 6 months</span>
                </div>
                <div className="patient-bar-chart" role="img" aria-label="Monthly appointment counts">
                  <div className="patient-bar-y-labels"><span>{maxMonthly}</span><span>{Math.ceil(maxMonthly * .66)}</span><span>{Math.ceil(maxMonthly * .33)}</span><span>0</span></div>
                  <div className="patient-bar-plot">
                    {[0, 1, 2, 3].map((line) => <div key={line} className="patient-bar-gridline" style={{ bottom: `${line * 33.333}%` }} />)}
                    <div className="patient-bar-columns">
                      {months.map((month) => (
                        <div className="patient-bar-column" key={`${month.label}-${month.total}`}>
                          <span className="patient-bar-tooltip" style={{ bottom: `calc(31px + ${(month.total / maxMonthly) * 85}%)` }}>{month.total}</span>
                          <div className="patient-bar-track">
                            {month.total > 0 ? (
                              <div className="patient-stacked-bar" style={{ height: `${Math.max(7, month.total / maxMonthly * 100)}%` }}>
                                {month.cancelled > 0 && <span className="bar-segment cancelled" style={{ flex: month.cancelled }} />}
                                {month.rescheduled > 0 && <span className="bar-segment rescheduled" style={{ flex: month.rescheduled }} />}
                                {month.scheduled > 0 && <span className="bar-segment scheduled" style={{ flex: month.scheduled }} />}
                                {month.completed > 0 && <span className="bar-segment completed" style={{ flex: month.completed }} />}
                                {(month.cancelled + month.rescheduled + month.scheduled + month.completed) < month.total && <span className="bar-segment other" style={{ flex: month.total - month.cancelled - month.rescheduled - month.scheduled - month.completed }} />}
                              </div>
                            ) : <div className="patient-empty-bar" />}
                          </div>
                          <span className="patient-bar-month">{month.label}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
                <div className="patient-line-legend patient-legend-new">
                  {counts.map((item) => <span key={item.label}><i style={{ background: item.color }} />{item.label}</span>)}
                </div>
              </div>
              <div className="patient-chart-panel patient-mix-panel patient-mix-panel-new">
                <div className="analytics-panel-heading">
                  <div><span className="analytics-icon-bubble purple">◔</span><h3>Appointment mix</h3></div>
                  <span>Status breakdown</span>
                </div>
                <div className="patient-donut-wrap">
                  <div className="patient-donut patient-donut-new" style={{ background: totalAppointments ? `conic-gradient(${gradient || "#173448 0% 100%"})` : "conic-gradient(#173448 0% 100%)" }} role="img" aria-label="Appointment status distribution">
                    <div className="patient-donut-center"><strong>{totalAppointments}</strong><span>Total visits</span></div>
                  </div>
                </div>
                <div className="patient-mix-legend patient-mix-legend-new">
                  {counts.map((item) => (
                    <div key={item.label}>
                      <span className="mix-dot" style={{ background: item.color }} />
                      <span>{item.label}</span>
                      <strong>{item.value}</strong>
                      <small>{totalAppointments ? Math.round(item.value / totalAppointments * 100) : 0}%</small>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          );
        })()}
        <div className="patient-chart-note"><span /> Based on your appointment records · Not a medical measurement</div>
      </section>

      <div className="dashboard-card services-preview-card">

        <div className="card-header">

          <div>
            <span className="section-label">
              HOSPITAL SERVICES
            </span>

            <h2>
              Healthcare services
            </h2>
          </div>

        </div>

        <div className="mini-services-grid">

          {HOSPITAL_SERVICES
            .slice(0, 4)
            .map((service) => (
              <div
                className="mini-service"
                key={service.title}
              >

                <div className="mini-service-icon">
                  {service.icon}
                </div>

                <div>
                  <strong>
                    {service.title}
                  </strong>

                  <span>
                    {service.description}
                  </span>
                </div>

              </div>
            ))}

        </div>

      </div>
    </>
  );
}

/* =========================================================
   STAT CARD
   ========================================================= */

function StatCard({
  icon,
  value,
  label,
}) {
  return (
    <div className="stat-card">

      <div className="stat-icon">
        {icon}
      </div>

      <div>
        <strong>
          {value}
        </strong>

        <span>
          {label}
        </span>
      </div>

    </div>
  );
}

/* =========================================================
   APPOINTMENT PREVIEW
   ========================================================= */

function AppointmentPreview({
  appointment,
}) {
  return (
    <div className="appointment-preview">

      <div className="appointment-date-box">

        <span>
          {appointment.appointment_date
            ? new Date(
                appointment.appointment_date
              ).toLocaleDateString(
                "en-IN",
                {
                  month: "short",
                }
              )
            : "---"}
        </span>

        <strong>
          {appointment.appointment_date
            ? new Date(
                appointment.appointment_date
              ).getDate()
            : "--"}
        </strong>

      </div>

      <div
        className="appointment-preview-doctor-photo"
        style={{
          width: 64,
          height: 64,
          minWidth: 64,
          borderRadius: 16,
          overflow: "hidden",
          display: "grid",
          placeItems: "center",
          background: "rgba(36, 214, 202, 0.12)",
          color: "#28d7ca",
          fontWeight: 800,
          alignSelf: "center",
        }}
      >
        {getDoctorPhoto(appointment) ? (
          <img
            src={getDoctorPhoto(appointment)}
            alt={`Portrait of Dr. ${appointment.doctor_name || appointment.doctor?.name || "Doctor"}`}
            loading="lazy"
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
            onError={(event) => {
              event.currentTarget.style.display = "none";
              event.currentTarget.parentElement.textContent = getDoctorInitials(appointment);
            }}
          />
        ) : (
          getDoctorInitials(appointment)
        )}
      </div>

      <div className="appointment-preview-info">

        <span className="appointment-specialty">
          {appointment.department_name ||
            "Healthcare"}
        </span>

        <h3>
          Dr.{" "}
          {appointment.doctor_name ||
            "Doctor"}
        </h3>

        <p>
          {formatTime(
            appointment.appointment_time
          )}
        </p>

      </div>

      <StatusBadge
        status={
          appointment.status
        }
      />

    </div>
  );
}

/* =========================================================
   PATIENT APPOINTMENTS
   ========================================================= */

function PatientAppointments({
  appointments,
  loading,
  onRefresh,
}) {
  return (
    <>
      <div className="dashboard-heading">

        <div>
          <span className="section-label">
            PATIENT PORTAL
          </span>

          <h1>
            Your{" "}
            <span>
              Appointments
            </span>
          </h1>

          <p>
            View and manage your scheduled
            healthcare appointments.
          </p>
        </div>

        <button
          className="refresh-button"
          onClick={onRefresh}
        >
          ↻ Refresh
        </button>

      </div>

      <div className="dashboard-card">

        {loading ? (
          <LoadingBox text="Loading your appointments..." />
        ) : appointments.length ===
          0 ? (
          <EmptyState
            icon="▣"
            title="No appointments yet"
            description="Use SmartCare AI to find a doctor and book an appointment."
          />
        ) : (
          <AppointmentList
            appointments={
              appointments
            }
          />
        )}

      </div>
    </>
  );
}

/* =========================================================
   APPOINTMENT LIST
   ========================================================= */

function AppointmentList({
  appointments,
}) {
  return (
    <div className="appointment-list">

      {appointments.map(
        (appointment) => (
          <div
            className="appointment-row"
            key={
              appointment.id ||
              appointment.appointment_id
            }
          >

            <div className="appointment-row-date">

              <strong>
                {formatDate(
                  appointment.appointment_date
                )}
              </strong>

              <span>
                {formatTime(
                  appointment.appointment_time
                )}
              </span>

            </div>

            <div className="appointment-row-doctor">

              <div
                className="table-avatar doctor-table-photo"
                style={{
                  width: 48,
                  height: 48,
                  minWidth: 48,
                  borderRadius: 12,
                  overflow: "hidden",
                  display: "grid",
                  placeItems: "center",
                  background: "rgba(36, 214, 202, 0.12)",
                  color: "#28d7ca",
                  fontWeight: 800,
                }}
              >
                {getDoctorPhoto(appointment) ? (
                  <img
                    src={getDoctorPhoto(appointment)}
                    alt={`Portrait of Dr. ${appointment.doctor_name || appointment.doctor?.name || "Doctor"}`}
                    loading="lazy"
                    style={{ width: "100%", height: "100%", objectFit: "cover" }}
                    onError={(event) => {
                      event.currentTarget.style.display = "none";
                      event.currentTarget.parentElement.textContent = getDoctorInitials(appointment);
                    }}
                  />
                ) : (
                  getDoctorInitials(appointment)
                )}
              </div>

              <div>

                <strong>
                  Dr.{" "}
                  {appointment.doctor_name ||
                    "Doctor"}
                </strong>

                <span>
                  {appointment.department_name ||
                    "Healthcare"}
                </span>

              </div>

            </div>

            <div className="appointment-row-reason">

              <span>
                Reason
              </span>

              <p>
                {appointment.reason ||
                  "General appointment"}
              </p>

            </div>

            <StatusBadge
              status={
                appointment.status
              }
            />

          </div>
        )
      )}

    </div>
  );
}

/* =========================================================
   STATUS BADGE
   ========================================================= */

function StatusBadge({
  status,
}) {
  const normalized =
    String(
      status || "SCHEDULED"
    ).toUpperCase();

  return (
    <span
      className={`status-badge status-${normalized.toLowerCase()}`}
    >
      {normalized}
    </span>
  );
}

/* =========================================================
   PATIENT SERVICES
   ========================================================= */

function PatientServices() {
  return (
    <>
      <div className="dashboard-heading">

        <div>
          <span className="section-label">
            SMARTCARE HOSPITAL
          </span>

          <h1>
            Hospital{" "}
            <span>
              Services
            </span>
          </h1>

          <p>
            Explore the healthcare services available
            through SmartCare.
          </p>
        </div>

      </div>

      <div className="services-grid dashboard-services">

        {HOSPITAL_SERVICES.map(
          (service) => (
            <div
              className="service-card"
              key={service.title}
            >

              <div className="service-icon">
                {service.icon}
              </div>

              <h3>
                {service.title}
              </h3>

              <p>
                {service.description}
              </p>

            </div>
          )
        )}

      </div>
    </>
  );
}

/* =========================================================
   PATIENT DOCTORS
   ========================================================= */

function PatientDoctors() {
  const [
    selectedSpecialization,
    setSelectedSpecialization,
  ] = useState("All");
  const { doctors, loadingDoctors, doctorsError } = useDoctors();

  const specializationNames = useMemo(
    () => [...new Set(doctors.map((doctor) => doctor.specialization).filter(Boolean))].sort(),
    [doctors]
  );

  const filteredDoctors = useMemo(() => {
    if (selectedSpecialization === "All") return doctors;
    return doctors.filter(
      (doctor) => doctor.specialization === selectedSpecialization
    );
  }, [doctors, selectedSpecialization]);

  return (
    <>
      <div className="dashboard-heading">

        <div>
          <span className="section-label">
            SMARTCARE HOSPITAL
          </span>

          <h1>
            Doctors &{" "}
            <span>
              Specializations
            </span>
          </h1>

          <p>
            Explore our doctors and medical
            specializations.
          </p>
        </div>

      </div>

      <div className="specialization-filter">

        <button
          className={
            selectedSpecialization ===
            "All"
              ? "filter-button active"
              : "filter-button"
          }
          onClick={() =>
            setSelectedSpecialization(
              "All"
            )
          }
        >
          All Doctors
        </button>

        {specializationNames.map((specialization) => (
          <button
            key={specialization}
            className={
              selectedSpecialization === specialization
                ? "filter-button active"
                : "filter-button"
            }
            onClick={() => setSelectedSpecialization(specialization)}
          >
            {specialization}
          </button>
        ))}

      </div>

      <div className="doctor-grid dashboard-doctor-grid">

        {loadingDoctors ? (
          <LoadingBox text="Loading doctors from the hospital directory..." />
        ) : doctorsError ? (
          <EmptyState
            icon="!"
            title="Doctors could not be loaded"
            description={`${doctorsError} Please check that the CareFlow backend is running.`}
          />
        ) : filteredDoctors.length === 0 ? (
          <EmptyState
            icon="◌"
            title="No doctors found"
            description="There are no active doctors for this specialization."
          />
        ) : (
          filteredDoctors.map((doctor) => (
            <DoctorCard doctor={doctor} key={doctor.id} />
          ))
        )}

      </div>
    </>
  );
}

/* =========================================================
   PATIENT AI CHATBOT
   IMPORTANT:
   AVAILABLE SLOTS ARE RENDERED INSIDE CHAT.
   THERE IS NO SEPARATE AVAILABLE SLOTS SECTION.
   ========================================================= */

function PatientAI({
  user,
  appointments = [],
  appointmentsLoading = false,
  onAppointmentsUpdated,
}) {
  const [messages, setMessages] =
    useState([
      {
        id: 1,
        role: "assistant",
        text:
          "Hello! I’m SmartCare AI. I can help you understand symptoms, find general home-care information and precautions, explore natural comfort measures, manage appointments, and answer hospital questions. I cannot diagnose conditions or prescribe medicines.",
      },
    ]);

  const [input, setInput] =
    useState("");

  const [loading, setLoading] =
    useState(false);

  const [booking, setBooking] =
    useState(false);

  const [selectedSlot, setSelectedSlot] = useState(null);
  const [rescheduleMode, setRescheduleMode] = useState(false);

  const messagesEndRef = useRef(null);
  const chatMessagesRef = useRef(null);

  // Keep one conversation ID for this mounted chat session.
  // The backend uses it to remember context such as the selected department.
  // A new chat component instance automatically receives a different ID.
  const conversationIdRef = useRef(
    `careflow-${Date.now()}-${Math.random().toString(36).slice(2, 12)}`
  );

  // Keep scrolling inside the conversation pane. Avoid scrollIntoView(),
  // which can move the entire dashboard page and hide the composer.
  useEffect(() => {
    const pane = chatMessagesRef.current;
    if (!pane) return;
    pane.scrollTo({
      top: pane.scrollHeight,
      behavior: window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
        ? "auto"
        : "smooth",
    });
  }, [messages, loading]);

  // Personalize the initial greeting after the patient's appointments load.
  useEffect(() => {
    if (appointmentsLoading || messages.length !== 1) return;
    const upcoming = appointments.filter(isUpcomingAppointment);
    setMessages([{
      id: 1,
      role: "assistant",
      text: upcoming.length
        ? `Welcome back! You have ${upcoming.length} upcoming appointment${upcoming.length === 1 ? "" : "s"}. I can help with symptoms, general home-care guidance, precautions, natural comfort measures, appointments, and hospital information.`
        : "Welcome to SmartCare AI. I can help with symptoms and general safety guidance, home-care information, precautions, natural comfort measures, hospital FAQs, and appointment booking. I don't diagnose or prescribe treatment.",
    }]);
  }, [appointments, appointmentsLoading]);

  // Secure backend confirmation returned after an AI action
  // asks the patient to confirm (for example, cancellation).
  const [pendingConfirmation, setPendingConfirmation] =
    useState(null);

  // Keep the most recently cancelled appointment in this chat session so
  // follow-up questions do not get mistaken for a new cancellation request.
  const [lastCancelledAppointment, setLastCancelledAppointment] =
    useState(null);
  const [pendingCancellationAppointment, setPendingCancellationAppointment] =
    useState(null);

  async function sendMessage(event) {
    if (event) {
      event.preventDefault();
    }

    const text =
      input.trim();

    if (!text || loading) {
      return;
    }

    const requestedMinutes =
      parseRequestedTime(text);

    setInput("");
    setSelectedSlot(null);

    setMessages(
      (current) => [
        ...current,
        {
          id: Date.now(),
          role: "user",
          text,
        },
      ]
    );

    // Resolve follow-up questions from the current chat context before
    // intent detection. Otherwise "Which appointment did I just cancel?"
    // can be misclassified as a request to cancel another appointment.
    const normalizedRequest = text.toLowerCase();
    const asksWhichWasCancelled =
      /\b(which|what)\s+(?:appointment|booking)\b.*\b(?:did i|have i)\b.*\bcancel(?:led|ed)?\b/i.test(text) ||
      /\bwhich appointment did i just cancel\b/i.test(text);
    const asksCancelledTime =
      /\b(what|when)\b.{0,35}\b(time|date|day)\b/i.test(text) &&
      /\b(appointment|that|it|cancelled|canceled)\b/i.test(text);
    const asksCancelledStatus =
      /\b(is|was|does|did)\b.{0,35}\b(that appointment|the appointment|it)\b.{0,25}\b(active|cancelled|canceled|status)\b/i.test(text) ||
      /\b(is that appointment still active)\b/i.test(text);

    if (lastCancelledAppointment && (asksWhichWasCancelled || asksCancelledTime || asksCancelledStatus)) {
      const remembered = lastCancelledAppointment;
      const doctorName = remembered.doctor_name || remembered.doctor?.name || remembered.doctor?.full_name || "your doctor";
      const dateValue = remembered.appointment_date || remembered.date;
      const timeValue = remembered.appointment_time || remembered.time;
      let memoryReply;

      if (asksCancelledStatus) {
        memoryReply = `No. Your appointment with Dr. ${String(doctorName).replace(/^Dr\.?\s*/i, "")} on ${formatDate(dateValue)} at ${formatTime(timeValue)} is cancelled.`;
      } else if (asksCancelledTime) {
        memoryReply = `The appointment you cancelled was with Dr. ${String(doctorName).replace(/^Dr\.?\s*/i, "")} on ${formatDate(dateValue)} at ${formatTime(timeValue)}.`;
      } else {
        memoryReply = `You cancelled your appointment with Dr. ${String(doctorName).replace(/^Dr\.?\s*/i, "")} on ${formatDate(dateValue)} at ${formatTime(timeValue)}. Its status is cancelled.`;
      }

      setMessages((current) => [...current, {
        id: Date.now() + 1,
        role: "assistant",
        text: memoryReply,
      }]);
      return;
    }

    // Answer appointment-list requests from the authenticated patient's
    // already-loaded appointment data, so the answer is accurate and immediate.
    const asksToManageAppointment =
      /\b(reschedule|reshedule|cancel|move|shift|postpone)\b/i.test(text);

    const asksUpcoming =
      !asksToManageAppointment &&
      /(upcoming|next|future).{0,35}appointments?|appointments?.{0,35}(upcoming|next|future)|show my appointments|my appointments/.test(normalizedRequest);
        if (asksUpcoming) {
          if (appointmentsLoading) {
            setLoading(true);
            setMessages((current) => [...current, {
              id: Date.now() + 1,
              role: "assistant",
              text: "I'm checking your appointments. Please try that request again in a moment.",
            }]);
            setLoading(false);
            return;
          }

      const upcoming = appointments
        .filter(isUpcomingAppointment)
        .sort((a, b) => {
          const aDate = `${a.appointment_date || a.date}T${a.appointment_time || a.time || "23:59:59"}`;
          const bDate = `${b.appointment_date || b.date}T${b.appointment_time || b.time || "23:59:59"}`;
          return new Date(aDate) - new Date(bDate);
        });

      const appointmentSummary = upcoming.length
        ? `Here ${upcoming.length === 1 ? "is your upcoming appointment" : "are your upcoming appointments"}:\n\n${upcoming.map((appointment, index) => {
            const doctor = appointment.doctor_name || appointment.doctor?.name || appointment.doctor?.full_name || "your doctor";
            const department = appointment.department_name || appointment.department || appointment.doctor?.department?.name;
            const date = formatDate(appointment.appointment_date || appointment.date);
            const time = formatTime(appointment.appointment_time || appointment.time);
            return `${index + 1}. Dr. ${String(doctor).replace(/^Dr\.?\s*/i, "")} — ${date} at ${time}${department ? ` (${department})` : ""}\n   Status: ${String(appointment.status || "SCHEDULED").toLowerCase()}`;
          }).join("\n\n")}\n\nWould you like help rescheduling or booking another appointment?`
        : "You don't have any upcoming appointments right now. If you'd like to book one, tell me the doctor or department you prefer (for example, Cardiology), and I'll show you available slots.";

      setMessages((current) => [...current, {
        id: Date.now() + 1,
        role: "assistant",
        text: appointmentSummary,
      }]);
      setPendingConfirmation(null);
      return;
    }

    setLoading(true);

    try {
      const requestBody = {
        message: text,
        conversation_id: conversationIdRef.current,
      };

      // Only send a confirmation token for an explicit Yes/No
      // reply to the pending confirmation. A new normal request
      // starts a fresh chatbot turn.
      const normalizedReply = text.toLowerCase();
      const isConfirmationReply = [
        "yes",
        "yes please",
        "y",
        "confirm",
        "confirmed",
        "sure",
        "okay",
        "ok",
        "no",
        "nope",
        "cancel",
        "don't",
        "do not",
      ].includes(normalizedReply);

      if (pendingConfirmation && isConfirmationReply) {
        requestBody.confirmation = pendingConfirmation;
      } else if (pendingConfirmation) {
        setPendingConfirmation(null);
      }
      const confirmationBeingSent = requestBody.confirmation;

      const data =
        await apiRequest(
          "/api/chat/",
          {
            method: "POST",
            body: JSON.stringify(requestBody),
          }
        );

      const responseText =
        extractChatText(data) ||
        "I found information related to your request.";

      const rawOptions =
        getBookingOptions(data);

      const rankedOptions =
        rankBookingOptions(
          rawOptions,
          requestedMinutes
        );
      const returnedIntent = String(
        data?.intent || data?.result?.intent || ""
      ).toUpperCase();

      const returnedAction = String(
        data?.action || data?.result?.action || ""
      ).toUpperCase();

      if (
        returnedIntent === "RESCHEDULE_APPOINTMENT" ||
        returnedAction.startsWith("RESCHEDULE")
      ) {
        setRescheduleMode(true);
      } else if (
        returnedIntent === "BOOK_APPOINTMENT" ||
        returnedAction === "AVAILABLE_SLOTS"
      ) {
        setRescheduleMode(false);
      }

      // Capture the exact appointment shown in the cancellation prompt.
      // This is more reliable than relying only on the confirmation token's
      // shape or on the appointment list having refreshed already.
      const returnedConfirmation =
        data?.confirmation || data?.result?.confirmation || null;
      const appointmentOptions =
        data?.appointment_options ||
        data?.result?.appointment_options ||
        [];

      if (
        returnedAction === "CANCEL_CONFIRMATION" &&
        Array.isArray(appointmentOptions) &&
        appointmentOptions.length === 1
      ) {
        setPendingCancellationAppointment(appointmentOptions[0]);
      }

      // On success, remember the appointment that was explicitly confirmed.
      // Fall back to the appointment list only if the prompt payload is absent.
      if (returnedAction === "CANCEL_SUCCESS") {
        const cancelledId =
          confirmationBeingSent?.appointment_id ||
          confirmationBeingSent?.appointmentId ||
          pendingCancellationAppointment?.id ||
          pendingCancellationAppointment?.appointment_id;
        const cancelledAppointment =
          pendingCancellationAppointment ||
          appointments.find(
            (appointment) => String(appointment.id ?? appointment.appointment_id) === String(cancelledId)
          );

        if (cancelledAppointment) {
          setLastCancelledAppointment({
            ...cancelledAppointment,
            status: "CANCELLED",
          });
        }
        setPendingCancellationAppointment(null);
        if (onAppointmentsUpdated) {
          await onAppointmentsUpdated();
        }
      } else if (returnedAction === "CONFIRMATION_CANCELLED" || returnedAction === "CANCEL_FAILED") {
        setPendingCancellationAppointment(null);
      }

      // Save a backend-issued confirmation token so a bare
      // "Yes" can safely execute only the action that was
      // explicitly shown to the patient.
      if (returnedConfirmation) {
        setPendingConfirmation(returnedConfirmation);
      } else {
        setPendingConfirmation(null);
      }

      setMessages(
        (current) => [
          ...current,
          {
            id: Date.now() + 1,
            role: "assistant",
            text: responseText,
            bookingOptions:
              rankedOptions,
          },
        ]
      );
    } catch (error) {
      setPendingConfirmation(null);

      setMessages(
        (current) => [
          ...current,
          {
            id: Date.now() + 1,
            role: "assistant",
            text:
              error.status === 401
                ? "Your session has expired. Please log in again."
                : extractErrorMessage(
                    error
                  ),
          },
        ]
      );
    } finally {
      setLoading(false);
    }
  }

  function selectSlot(slot) {
    setSelectedSlot(slot);
  }

  async function confirmBooking() {
    if (!selectedSlot || booking) {
      return;
    }

    setBooking(true);

    try {
      const doctorId = slotDoctorId(selectedSlot);
      const date = normalizeSlotDate(slotDate(selectedSlot));
      const time = normalizeSlotTime(slotTime(selectedSlot));

      if (!doctorId || !date || !time) {
        throw new Error("The selected appointment slot is incomplete.");
      }

      // Rescheduling must go through the chatbot's secure confirmation flow.
      // Never create a second appointment for a reschedule.
      if (rescheduleMode) {
        const data = await apiRequest("/api/chat/", {
          method: "POST",
          body: JSON.stringify({
            message: `Reschedule my appointment to ${date} at ${time}`,
            conversation_id: conversationIdRef.current,
          }),
        });

        const confirmation =
          data?.confirmation || data?.result?.confirmation;

        const firstResponseText =
          extractChatText(data) ||
          "I couldn't process that rescheduling request.";

        // A slot is not rescheduled unless the backend issues a
        // signed confirmation token for the specific appointment.
        if (!confirmation?.token) {
          setPendingConfirmation(null);
          setMessages((current) => [
            ...current,
            {
              id: Date.now(),
              role: "assistant",
              text: firstResponseText,
              bookingOptions: [],
            },
          ]);
          setSelectedSlot(null);
          return;
        }

        // Clicking the explicit Confirm button is the patient's
        // confirmation. Send the backend-issued token with "yes".
        const result = await apiRequest("/api/chat/", {
          method: "POST",
          body: JSON.stringify({
            message: "yes",
            confirmation,
            conversation_id: conversationIdRef.current,
          }),
        });

        const resultAction = String(
          result?.action || result?.result?.action || ""
        ).toUpperCase();

        const resultText =
          extractChatText(result) ||
          "I couldn't verify whether the appointment was rescheduled.";

        setPendingConfirmation(
          resultAction === "RESCHEDULE_SUCCESS"
            ? null
            : result?.confirmation || result?.result?.confirmation || null
        );

        setMessages((current) => [
          ...current,
          {
            id: Date.now() + 1,
            role: "assistant",
            text: resultText,
            bookingOptions: [],
          },
        ]);

        setSelectedSlot(null);

        // Only exit reschedule mode and refresh the appointment list
        // when the backend explicitly reports a successful update.
        if (resultAction === "RESCHEDULE_SUCCESS") {
          setRescheduleMode(false);
          if (onAppointmentsUpdated) {
            await onAppointmentsUpdated();
          }
        }

        return;
      }

      // Normal new appointment booking remains unchanged.
      const appointment = await apiRequest("/api/appointments/", {
        method: "POST",
        body: JSON.stringify({
          doctor: Number(doctorId),
          appointment_date: date,
          appointment_time: time,
          status: "SCHEDULED",
          reason: "Booked through SmartCare AI",
        }),
      });

      setMessages((current) => [
        ...current,
        {
          id: Date.now(),
          role: "assistant",
          text: `Appointment confirmed with Dr. ${slotDoctorName(
            selectedSlot
          )} on ${formatDate(date)} at ${formatTime(time)}. Appointment ID: ${
            appointment?.appointment_id || appointment?.id || "confirmed"
          }.`,
        },
      ]);

      setSelectedSlot(null);
      setRescheduleMode(false);

      if (onAppointmentsUpdated) {
        onAppointmentsUpdated();
      }
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          id: Date.now(),
          role: "assistant",
          text: `I could not complete the ${
            rescheduleMode ? "rescheduling" : "booking"
          }. ${extractErrorMessage(error)}`,
        },
      ]);
    } finally {
      setBooking(false);
    }
  }

  return (
    <>
      {/* =====================================================
          CHAT PAGE HEADER
          ===================================================== */}

      <div className="dashboard-heading">

        <div>

          <span className="section-label">
            SMARTCARE AI
          </span>

          <h1>
            AI{" "}
            <span>
              Chatbot
            </span>
          </h1>

          <p>
            Tell me what you need in natural language.
          </p>

        </div>

        <div className="ai-status-pill">
          <span></span>
          AI Assistant Online
        </div>

      </div>

      {/* =====================================================
          CHAT LAYOUT
          ===================================================== */}

      <div className="ai-chat-layout careflow-chat-layout">

        <div className="chat-card">

          {/* CHAT HEADER */}

          <div className="chat-header">

            <div className="ai-icon robot-avatar" aria-label="SmartCare AI robot">
              <span role="img" aria-label="robot">🤖</span>
            </div>

            <div className="chat-header-text">

              <strong>
                SmartCare AI Assistant
              </strong>

              <span>
                Appointment & hospital communication
              </span>

            </div>

            <div className="chat-patient-blood-group" title="Patient blood group">
              <span aria-hidden="true">♥</span>
              <span>Blood group</span>
              <strong>{readBloodGroup(user) || "Not set"}</strong>
            </div>

            <div className="online-dot"></div>

          </div>

          {/* =================================================
              CHAT MESSAGES
              ================================================= */}

          <div className="chat-messages" ref={chatMessagesRef}>

            {messages.map(
              (message) => (
                <div
                  key={message.id}
                  className={`chat-message ${
                    message.role ===
                    "user"
                      ? "chat-message-user"
                      : "chat-message-ai"
                  }`}
                >

                  {/* MESSAGE */}

                  <div className="message-bubble">

                    {message.role ===
                      "assistant" && (
                      <div className="message-ai-icon robot-avatar" aria-label="SmartCare AI robot">
                        <span role="img" aria-label="robot">🤖</span>
                      </div>
                    )}

                    <div className="message-content">
                      {message.text}
                    </div>

                  </div>

                  {/* =================================================
                      BOOKING OPTIONS
                      THEY ARE INSIDE THE CHAT MESSAGE
                      ================================================= */}

                  {message.role ===
                    "assistant" &&
                    Array.isArray(
                      message.bookingOptions
                    ) &&
                    message.bookingOptions
                      .length > 0 && (
                      <div className="chat-booking-options">

                        <div className="chat-booking-title">

                          <div>

                            <span>
                              AVAILABLE SLOTS
                            </span>

                            <strong>
                              Choose a doctor and time
                            </strong>

                          </div>

                          <small>
                            {
                              message
                                .bookingOptions
                                .length
                            }{" "}
                            relevant slots
                          </small>

                        </div>

                        <div className="chat-slot-grid">

                          {message.bookingOptions.map(
                            (
                              slot,
                              index
                            ) => {
                              const doctorName =
                                slotDoctorName(
                                  slot
                                );

                              const department =
                                slotDepartment(
                                  slot
                                );

                              const date =
                                slotDate(
                                  slot
                                );

                              const time =
                                slotTime(
                                  slot
                                );

                              const fee =
                                slotFee(
                                  slot
                                );

                              const isSelected =
                                selectedSlot &&
                                String(
                                  slotDoctorId(
                                    selectedSlot
                                  )
                                ) ===
                                  String(
                                    slotDoctorId(
                                      slot
                                    )
                                  ) &&
                                normalizeSlotDate(
                                  slotDate(
                                    selectedSlot
                                  )
                                ) ===
                                  normalizeSlotDate(
                                    date
                                  ) &&
                                normalizeSlotTime(
                                  slotTime(
                                    selectedSlot
                                  )
                                ) ===
                                  normalizeSlotTime(
                                    time
                                  );

                              return (
                                <div
                                  key={`${slotDoctorId(
                                    slot
                                  )}-${date}-${time}-${index}`}
                                  className={`chat-slot-card ${
                                    isSelected
                                      ? "chat-slot-selected"
                                      : ""
                                  }`}
                                >

                                  <div className="chat-slot-top">

                                    <span className="slot-period">
                                      {
                                        formatTime(
                                          time
                                        ).split(
                                          " "
                                        )[1]
                                      }
                                    </span>

                                    {isSelected && (
                                      <span className="slot-selected-badge">
                                        ✓ Selected
                                      </span>
                                    )}

                                  </div>

                                  <div className="chat-slot-doctor">
                                    Dr.{" "}
                                    {
                                      doctorName
                                    }
                                  </div>

                                  <div className="chat-slot-department">
                                    {
                                      department
                                    }
                                  </div>

                                  <div className="chat-slot-date">
                                    {
                                      formatDate(
                                        date
                                      )
                                    }
                                  </div>

                                  <div className="chat-slot-time">
                                    {
                                      formatTime(
                                        time
                                      )
                                    }
                                  </div>

                                  {fee !==
                                    null &&
                                    fee !==
                                      undefined &&
                                    fee !==
                                      "" && (
                                      <div className="chat-slot-fee">
                                        {
                                          formatFee(
                                            fee
                                          )
                                        }
                                      </div>
                                    )}

                                  <button
                                    type="button"
                                    className={
                                      isSelected
                                        ? "chat-slot-button selected"
                                        : "chat-slot-button"
                                    }
                                    onClick={() =>
                                      selectSlot(
                                        slot
                                      )
                                    }
                                  >
                                    {isSelected
                                      ? "Selected ✓"
                                      : "Select this slot →"}
                                  </button>

                                </div>
                              );
                            }
                          )}

                        </div>

                        {/* =================================================
                            CONFIRMATION
                            ================================================= */}

                        {selectedSlot && (
                          <div className="booking-confirm-panel">

                            <div className="booking-confirm-info">

                              <div className="booking-confirm-icon">
                                ✓
                              </div>

                              <div>

                                <span>
                                  SELECTED APPOINTMENT
                                </span>

                                <strong>
                                  Dr.{" "}
                                  {
                                    slotDoctorName(
                                      selectedSlot
                                    )
                                  }
                                </strong>

                                <small>
                                  {
                                    formatDate(
                                      slotDate(
                                        selectedSlot
                                      )
                                    )
                                  }{" "}
                                  •{" "}
                                  {
                                    formatTime(
                                      slotTime(
                                        selectedSlot
                                      )
                                    )
                                  }
                                </small>

                              </div>

                            </div>

                            <div className="booking-confirm-actions">

                              <button
                                type="button"
                                className="button button-ghost"
                                onClick={() =>
                                  setSelectedSlot(
                                    null
                                  )
                                }
                                disabled={
                                  booking
                                }
                              >
                                Change
                              </button>

                              <button
                                type="button"
                                className="button button-primary"
                                onClick={
                                  confirmBooking
                                }
                                disabled={
                                  booking
                                }
                              >
                                {booking
                                  ? (rescheduleMode ? "Rescheduling..." : "Booking...")
                                  : (rescheduleMode ? "Request Reschedule" : "Confirm Appointment")
                                }
                              </button>
                            </div>

                          </div>
                        )}

                      </div>
                    )}

                </div>
              )
            )}

            {/* TYPING */}

            {loading && (
              <div className="chat-message chat-message-ai">

                <div className="message-bubble">

                  <div className="message-ai-icon robot-avatar" aria-label="SmartCare AI robot">
                    <span role="img" aria-label="robot">🤖</span>
                  </div>

                  <div className="typing-indicator">

                    <span></span>
                    <span></span>
                    <span></span>

                  </div>

                </div>

              </div>
            )}

            <div ref={messagesEndRef} className="chat-scroll-anchor" aria-hidden="true" />
          </div>

          {/* =================================================
              QUICK ACTIONS
              ================================================= */}

          <div className="chat-quick-actions" aria-label="SmartCare AI quick actions">

            <button type="button" className="chat-action-symptoms" onClick={() => setInput("I would like general guidance about my symptoms and when I should seek medical care.")}>
              <span aria-hidden="true">✚</span> Symptoms & Guidance
            </button>

            <button type="button" className="chat-action-homecare" onClick={() => setInput("Please share general home-care information and natural comfort measures for my symptoms.")}>
              <span aria-hidden="true">✿</span> Home Care & Natural Relief
            </button>

            <button type="button" className="chat-action-precautions" onClick={() => setInput("What precautions should I take and what should I avoid for my symptoms?")}>
              <span aria-hidden="true">◇</span> Precautions
            </button>

            <button type="button" className="chat-action-booking" onClick={() => setInput("I want to book a general appointment. Please help me choose a department and available slot.")}>
              <span aria-hidden="true">▦</span> Book Appointment
            </button>

            <button type="button" className="chat-action-appointments" onClick={() => setInput("Show my upcoming appointments.")}>
              <span aria-hidden="true">▤</span> My Appointments
            </button>

            <button type="button" className="chat-action-hospital" onClick={() => setInput("Please tell me about hospital services, departments, and timings.")}>
              <span aria-hidden="true">＋</span> Hospital Help
            </button>

          </div>

          {/* =================================================
              INPUT
              ================================================= */}

          <form
            className="chat-input-area"
            onSubmit={
              sendMessage
            }
          >

            <input
              value={input}
              onChange={(event) =>
                setInput(
                  event.target.value
                )
              }
              placeholder="Type your healthcare request..."
              disabled={loading}
            />

            <button
              type="submit"
              className="chat-send-button"
              disabled={
                loading ||
                !input.trim()
              }
            >
              →
            </button>

          </form>

          <div className="chat-disclaimer">
            SmartCare is designed for appointment and
            communication workflows. It does not diagnose
            medical conditions or prescribe treatment.
          </div>

        </div>

        {/* =================================================
            AI SIDEBAR
            ================================================= */}

        <aside className="ai-sidebar">

          <div className="ai-sidebar-card">

            <div className="ai-sidebar-header">

              <span>
                SMARTCARE AI
              </span>

              <strong>
                Workflow
              </strong>

            </div>

            <WorkflowStep
              number="01"
              title="Understand"
              description="SLM intent classification"
              active
            />

            <WorkflowStep
              number="02"
              title="Retrieve"
              description="RAG knowledge retrieval"
              active
            />

            <WorkflowStep
              number="03"
              title="Safety"
              description="Safety classification"
            />

            <WorkflowStep
              number="04"
              title="Execute"
              description="Workflow automation"
            />

          </div>

          <div className="ai-sidebar-card">

            <div className="ai-sidebar-header">

              <span>
                KNOWLEDGE SOURCES
              </span>

            </div>

            <KnowledgeItem>
              Hospital FAQs
            </KnowledgeItem>

            <KnowledgeItem>
              Doctor information
            </KnowledgeItem>

            <KnowledgeItem>
              Appointment database
            </KnowledgeItem>

            <KnowledgeItem>
              Patient communication
            </KnowledgeItem>

          </div>

        </aside>

      </div>
    </>
  );
}

/* =========================================================
   WORKFLOW STEP
   ========================================================= */

function WorkflowStep({
  number,
  title,
  description,
  active = false,
}) {
  return (
    <div
      className={`workflow-step ${
        active ? "active" : ""
      }`}
    >

      <div>
        {number}
      </div>

      <div>

        <strong>
          {title}
        </strong>

        <span>
          {description}
        </span>

      </div>

      <span>
        {active ? "✓" : "−"}
      </span>

    </div>
  );
}

/* =========================================================
   KNOWLEDGE ITEM
   ========================================================= */

function KnowledgeItem({
  children,
}) {
  return (
    <div className="knowledge-item">

      <span>
        ◆
      </span>

      {children}

    </div>
  );
}

/* =========================================================
   DOCTOR DASHBOARD
   ========================================================= */

function DoctorDashboard({
  user,
  onLogout,
}) {
  const [appointments, setAppointments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState("overview");
  const [availability, setAvailability] = useState([]);
  const [availabilityLoading, setAvailabilityLoading] = useState(false);
  const [availabilityError, setAvailabilityError] = useState("");
  const [availabilityMessage, setAvailabilityMessage] = useState("");
  const [slotForm, setSlotForm] = useState({ date: getTomorrowISO(), start_time: "09:00", end_time: "12:00", slot_duration: "30" });
  const [chartYear, setChartYear] = useState(String(new Date().getFullYear()));

  async function loadAppointments() {
    setLoading(true);
    setError("");
    try {
      const data = await apiRequest("/api/appointments/");
      setAppointments(normalizeListResponse(data));
    } catch (err) {
      if (err.status === 401) { onLogout(); return; }
      setError(extractErrorMessage(err));
    } finally { setLoading(false); }
  }

  async function loadAvailability() {
    setAvailabilityLoading(true);
    setAvailabilityError("");
    try {
      // This endpoint should return the authenticated doctor's availability records.
      const data = await apiRequest("/api/doctors/availability/");
      setAvailability(normalizeListResponse(data?.results ? data : data?.availability ? { results: data.availability } : data));
    } catch (err) {
      if (err.status === 401) { onLogout(); return; }
      setAvailabilityError("Availability could not be loaded. Confirm that GET /api/doctors/availability/ is configured in Django.");
    } finally { setAvailabilityLoading(false); }
  }

  useEffect(() => { loadAppointments(); loadAvailability(); }, []);

  const statusOf = (item) => String(item?.status || "SCHEDULED").toUpperCase();
  const scheduledCount = appointments.filter((a) => ["SCHEDULED", "CONFIRMED", "PENDING"].includes(statusOf(a))).length;
  const rescheduledCount = appointments.filter((a) => ["RESCHEDULED", "RESCHEDULE"].includes(statusOf(a))).length;
  const completedCount = appointments.filter((a) => statusOf(a) === "COMPLETED").length;
  const cancelledCount = appointments.filter((a) => statusOf(a) === "CANCELLED").length;
  const otherCount = Math.max(0, appointments.length - scheduledCount - rescheduledCount - completedCount - cancelledCount);

  const monthlyStats = useMemo(() => {
    const labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    return labels.map((label, month) => {
      const records = appointments.filter((a) => {
        const raw = a.appointment_date || a.date;
        if (!raw) return false;
        const date = parseDateOnly(raw);
        return date && date.getFullYear() === Number(chartYear) && date.getMonth() === month;
      });
      return { label, total: records.length, scheduled: records.filter((a) => ["SCHEDULED", "CONFIRMED", "PENDING"].includes(statusOf(a))).length, completed: records.filter((a) => statusOf(a) === "COMPLETED").length, cancelled: records.filter((a) => statusOf(a) === "CANCELLED").length, rescheduled: records.filter((a) => ["RESCHEDULED", "RESCHEDULE"].includes(statusOf(a))).length };
    });
  }, [appointments, chartYear]);
  const maxMonthly = Math.max(1, ...monthlyStats.map((m) => m.total));
  const currentYear = new Date().getFullYear();
  const years = Array.from(new Set([String(currentYear - 1), String(currentYear), ...appointments.map((a) => { const d = parseDateOnly(a.appointment_date || a.date); return d ? String(d.getFullYear()) : null; }).filter(Boolean)])).sort().reverse();

  async function releaseSlots(event) {
    event.preventDefault();
    setAvailabilityError(""); setAvailabilityMessage("");
    if (slotForm.end_time <= slotForm.start_time) { setAvailabilityError("End time must be later than start time."); return; }
    try {
      await apiRequest("/api/doctors/availability/", { method: "POST", body: JSON.stringify({ date: slotForm.date, start_time: slotForm.start_time, end_time: slotForm.end_time, slot_duration: Number(slotForm.slot_duration) }) });
      setAvailabilityMessage("Availability released successfully.");
      await loadAvailability();
    } catch (err) {
      setAvailabilityError(err.status === 401 ? "Your session has expired. Please sign in again." : "Could not release slots. Ensure Django supports POST /api/doctors/availability/ with date, start_time, end_time and slot_duration.");
    }
  }

  async function removeAvailability(item) {
    const id = item.id || item.pk;
    if (!id) { setAvailabilityError("This availability record has no ID, so it cannot be removed."); return; }
    setAvailabilityError(""); setAvailabilityMessage("");
    try {
      await apiRequest(`/api/doctors/availability/${encodeURIComponent(id)}/`, { method: "DELETE" });
      setAvailabilityMessage("Availability removed.");
      await loadAvailability();
    } catch (err) {
      setAvailabilityError("Could not remove this slot. Ensure Django supports DELETE /api/doctors/availability/{id}/.");
    }
  }

  return (
    <div className="dashboard-page doctor-dashboard-page">
      <DashboardTopbar user={user} onLogout={onLogout} />
      <div className="doctor-dashboard-shell">
        <div className="doctor-welcome-panel">
          <div className="doctor-welcome-copy">
            <span className="section-label">CLINICIAN PORTAL</span>
            <h1>Dr. <span>{user?.name || "Doctor"}</span></h1>
            <p>{user?.department || user?.specialization || "Healthcare"} · Your practice, appointments and availability in one place.</p>
            <div className="doctor-welcome-tags"><span>✦ SmartCare Intelligence</span><span>● Secure workspace</span></div>
          </div>
          <div className="doctor-welcome-avatar doctor-welcome-photo" aria-label={`Profile photo of Dr. ${user?.name || "Doctor"}`}>
            <img
              src={DEMO_DOCTORS.find((doctor) => (user?.name || "").toLowerCase().includes(doctor.name.toLowerCase()))?.photo || `${import.meta.env.BASE_URL}doctors/dr-arjun-mehta.png`}
              alt={`Dr. ${user?.name || "Doctor"}`}
              onError={(event) => { event.currentTarget.style.display = "none"; event.currentTarget.parentElement.classList.add("doctor-photo-fallback"); event.currentTarget.parentElement.insertAdjacentText("afterbegin", (user?.name || "DR").split(" ").map((part) => part[0]).join("").slice(0, 2)); }}
            />
            <i>✓</i>
          </div>
          <button className="refresh-button doctor-refresh" onClick={() => { loadAppointments(); loadAvailability(); }}>↻ Refresh data</button>
        </div>

        <div className="doctor-dashboard-tabs" role="tablist" aria-label="Doctor dashboard sections">
          {[ ["overview", "Overview"], ["appointments", "Appointments"], ["availability", "Manage availability"] ].map(([id, label]) => <button key={id} role="tab" aria-selected={activeTab === id} className={activeTab === id ? "active" : ""} onClick={() => setActiveTab(id)}>{label}</button>)}
        </div>

        {error && <div className="error-message">{error}</div>}

        {activeTab !== "availability" && <div className="overview-stat-grid doctor-stat-grid">
          <StatCard icon="▣" value={appointments.length} label="Total appointments" />
          <StatCard icon="◷" value={scheduledCount} label="Scheduled / confirmed" />
          <StatCard icon="✓" value={completedCount} label="Completed" />
          <StatCard icon="↗" value={cancelledCount} label="Cancelled" />
        </div>}

        {activeTab === "overview" && <>
          <section className="doctor-analytics-card dashboard-card">
            <div className="doctor-section-heading"><div><span className="section-label">PRACTICE ANALYTICS</span><h2>Appointments by month</h2><p>Monthly distribution from the appointment records available to your account.</p></div><label className="doctor-year-select">Year <select value={chartYear} onChange={(event) => setChartYear(event.target.value)}>{years.map((year) => <option key={year} value={year}>{year}</option>)}</select></label></div>
            <div className="doctor-chart-legend"><span><i className="legend-total"/>All appointments</span><span><i className="legend-scheduled"/>Scheduled</span><span><i className="legend-completed"/>Completed</span><span><i className="legend-cancelled"/>Cancelled</span><span><i className="legend-rescheduled"/>Rescheduled</span></div>
            <div className="doctor-month-chart" aria-label={`Monthly appointment counts for ${chartYear}`}>
              {monthlyStats.map((month) => <div className="doctor-month-column" key={month.label} title={`${month.label}: ${month.total} appointments`}><div className="doctor-month-bar-area"><span className="doctor-month-value">{month.total || ""}</span><div className="doctor-month-bar-stack" style={{ height: `${Math.max(month.total ? 8 : 2, month.total / maxMonthly * 100)}%` }}><span className="bar-scheduled" style={{ height: `${month.total ? month.scheduled / month.total * 100 : 0}%` }}/><span className="bar-completed" style={{ height: `${month.total ? month.completed / month.total * 100 : 0}%` }}/><span className="bar-rescheduled" style={{ height: `${month.total ? month.rescheduled / month.total * 100 : 0}%` }}/><span className="bar-other" style={{ height: `${month.total ? month.cancelled / month.total * 100 : 0}%` }}/></div></div><span className="doctor-month-label">{month.label}</span></div>)}
            </div>
            <div className="doctor-chart-footnote">The chart reflects appointment records available to this login; it is not a forecast.</div>
            <div className="doctor-analytics-lower-grid">
              <section className="doctor-status-card"><div><span className="section-label">APPOINTMENT MIX</span><h3>Status distribution</h3><p>Live appointment records by status</p></div>
                {(() => {
                  const items = [{label:"Scheduled",value:scheduledCount,color:"#4c9cff"},{label:"Rescheduled",value:rescheduledCount,color:"#b784ff"},{label:"Completed",value:completedCount,color:"#4ee0a4"},{label:"Cancelled",value:cancelledCount,color:"#ff8d78"},{label:"Other",value:otherCount,color:"#ffca66"}];
                  const rawTotal = items.reduce((sum,item)=>sum+item.value,0); let cumulative=0;
                  const segments=items.filter(item=>item.value>0).map(item=>{const from=cumulative/Math.max(1,rawTotal)*100;cumulative+=item.value;return `${item.color} ${from}% ${cumulative/Math.max(1,rawTotal)*100}%`;});
                  const pieBackground=rawTotal>0?`conic-gradient(${segments.join(", ")})`:"conic-gradient(#1a3445 0% 100%)";
                  return <div className="doctor-pie-layout"><div className="doctor-pie-chart" style={{background:pieBackground}} role="img" aria-label="Appointment status pie chart"><div><strong>{rawTotal}</strong><span>Total records</span></div></div><div className="doctor-pie-legend">{items.map(item=><div key={item.label}><span style={{background:item.color}}/><span>{item.label}</span><strong>{item.value}</strong></div>)}</div></div>;
                })()}
              </section>
              <section className="doctor-status-card doctor-insights-card"><span className="section-label">PRACTICE SNAPSHOT</span><h3>Quick insights</h3>
                <div className="doctor-insight-tile"><span className="insight-icon blue">◷</span><div><strong>{scheduledCount}</strong><span>Scheduled appointments</span></div></div>
                <div className="doctor-insight-tile"><span className="insight-icon purple">↻</span><div><strong>{rescheduledCount}</strong><span>Rescheduled appointments</span></div></div>
                <div className="doctor-insight-tile"><span className="insight-icon green">✓</span><div><strong>{completedCount}</strong><span>Completed appointments</span></div></div>
                <div className="doctor-insight-tile"><span className="insight-icon coral">×</span><div><strong>{cancelledCount}</strong><span>Cancelled appointments</span></div></div>
              </section>
            </div>
          </section>
          <section className="dashboard-card doctor-upcoming-card"><div className="card-header"><div><span className="section-label">PATIENT SCHEDULE</span><h2>Recent appointments</h2></div><button className="text-button" onClick={() => setActiveTab("appointments")}>View all →</button></div>{loading?<LoadingBox text="Loading appointments..."/>:appointments.length?<DoctorAppointmentTable appointments={[...appointments].sort((a,b)=>String(b.appointment_date||b.date||"").localeCompare(String(a.appointment_date||a.date||""))).slice(0,5)}/>:<EmptyState icon="▣" title="No appointments yet" description="When patients book appointments, they will appear here."/>}</section>
        </>}

        {activeTab === "appointments" && <section className="dashboard-card doctor-upcoming-card">
          <div className="card-header"><div><span className="section-label">APPOINTMENT DATABASE</span><h2>Booked appointments</h2></div><span className="table-count">{appointments.length} records</span></div>
          {loading ? <LoadingBox text="Loading patient appointments..."/> : appointments.length ? <DoctorAppointmentTable appointments={appointments}/> : <EmptyState icon="▣" title="No appointments" description="There are currently no appointments booked with you."/>}
        </section>}

        {activeTab === "availability" && <section className="doctor-availability-layout">
          <div className="dashboard-card doctor-slot-form-card"><div className="card-header"><div><span className="section-label">SLOT MANAGEMENT</span><h2>Release appointment slots</h2></div><span className="availability-icon">＋</span></div><p className="card-description">Publish the hours you are available so patients can book a suitable appointment.</p>
            <form className="doctor-slot-form" onSubmit={releaseSlots}>
              <label>Date<input type="date" min={localDateToISO(new Date())} value={slotForm.date} onChange={(e) => setSlotForm((s) => ({ ...s, date: e.target.value }))} required/></label>
              <div className="doctor-slot-form-row"><label>Start time<input type="time" value={slotForm.start_time} onChange={(e) => setSlotForm((s) => ({ ...s, start_time: e.target.value }))} required/></label><label>End time<input type="time" value={slotForm.end_time} onChange={(e) => setSlotForm((s) => ({ ...s, end_time: e.target.value }))} required/></label></div>
              <label>Appointment duration<select value={slotForm.slot_duration} onChange={(e) => setSlotForm((s) => ({ ...s, slot_duration: e.target.value }))}><option value="15">15 minutes</option><option value="20">20 minutes</option><option value="30">30 minutes</option><option value="45">45 minutes</option><option value="60">60 minutes</option></select></label>
              <div className="doctor-slot-preview"><span>PREVIEW</span><strong>{formatDate(slotForm.date)} · {slotForm.start_time || "--:--"}–{slotForm.end_time || "--:--"}</strong><small>Slots will be generated at {slotForm.slot_duration}-minute intervals.</small></div>
              {availabilityError && <div className="error-message">{availabilityError}</div>}{availabilityMessage && <div className="success-message">{availabilityMessage}</div>}
              <button className="auth-submit" type="submit">＋ Release availability</button>
            </form>
          </div>
          <div className="dashboard-card doctor-released-slots"><div className="card-header"><div><span className="section-label">YOUR CALENDAR</span><h2>Released availability</h2></div><button className="text-button" onClick={loadAvailability}>↻ Refresh</button></div>
            {availabilityLoading ? <LoadingBox text="Loading availability..."/> : availability.length ? <div className="released-slot-list">{availability.map((item) => <div className="released-slot-row" key={item.id || item.pk || `${item.date}-${item.start_time}`}><div className="released-slot-date"><strong>{formatDate(item.date || item.available_date || item.start_date)}</strong><span>{formatTime(item.start_time || item.start_time_display)} – {formatTime(item.end_time || item.end_time_display)}</span></div><span className={`availability-status ${(item.is_active === false || item.status === "CANCELLED") ? "inactive" : "active"}`}>{(item.is_active === false || item.status === "CANCELLED") ? "Inactive" : "Available"}</span><button className="remove-slot-button" onClick={() => removeAvailability(item)} aria-label="Remove availability">×</button></div>)}</div> : <EmptyState icon="◷" title="No availability released" description="Use the form to publish the dates and hours patients can book."/>}
            <p className="doctor-api-note">Availability actions require matching authenticated Django endpoints. Existing booked appointments should never be deleted when availability is changed.</p>
          </div>
        </section>}
      </div>
    </div>
  );
}

/* =========================================================
   DOCTOR APPOINTMENT TABLE
   ========================================================= */

function DoctorAppointmentTable({
  appointments,
}) {
  return (
    <div className="doctor-table-wrapper">

      <table className="doctor-table">

        <thead>

          <tr>

            <th>
              Appointment
            </th>

            <th>
              Patient
            </th>

            <th>
              Contact
            </th>

            <th>
              Date & Time
            </th>

            <th>
              Reason
            </th>

            <th>
              Status
            </th>

          </tr>

        </thead>

        <tbody>

          {appointments.map(
            (appointment) => (
              <tr
                key={
                  appointment.id ||
                  appointment.appointment_id
                }
              >

                <td>

                  <strong className="appointment-id">
                    #
                    {appointment.appointment_id ||
                      appointment.id}
                  </strong>

                </td>

                <td>

                  <div className="patient-table-person">

                    <div className="table-avatar">
                      {(
                        appointment.patient_name ||
                        "P"
                      )
                        .split(" ")
                        .map(
                          (part) =>
                            part[0]
                        )
                        .join("")
                        .slice(
                          0,
                          2
                        )}
                    </div>

                    <div>

                      <strong>
                        {
                          appointment.patient_name ||
                          "Patient"
                        }
                      </strong>

                      <span>
                        Patient
                      </span>
                      <span className="patient-table-blood-group">
                        <span aria-hidden="true">♥</span>
                        Blood group: {getNestedValue(appointment, ["patient_blood_group", "blood_group", "patient.blood_group", "patient.profile.blood_group", "patient_profile.blood_group", "patientProfile.blood_group"]) || "Not set"}
                      </span>

                    </div>

                  </div>

                </td>

                <td>

                  <div className="contact-cell">

                    <span>
                      {
                        appointment.patient_email ||
                        "—"
                      }
                    </span>

                    <span>
                      {
                        appointment.patient_mobile ||
                        "—"
                      }
                    </span>

                  </div>

                </td>

                <td>

                  <div className="date-time-cell">

                    <strong>
                      {
                        formatDate(
                          appointment.appointment_date
                        )
                      }
                    </strong>

                    <span>
                      {
                        formatTime(
                          appointment.appointment_time
                        )
                      }
                    </span>

                  </div>

                </td>

                <td>

                  <span className="reason-cell">
                    {
                      appointment.reason ||
                      "General appointment"
                    }
                  </span>

                </td>

                <td>

                  <StatusBadge
                    status={
                      appointment.status
                    }
                  />

                </td>

              </tr>
            )
          )}

        </tbody>

      </table>

    </div>
  );
}

/* =========================================================
   MAIN APP
   ========================================================= */

export default function App() {
  const [page, setPage] =
    useState("home");

  const [user, setUser] =
    useState(null);

  const [initializing, setInitializing] =
    useState(true);

  useEffect(() => {
    let cancelled = false;

    async function initializeApp() {
      const storedUser = getStoredUser();
      const token = getToken();

      if (storedUser && token) {
        const resolvedUser =
          storedUser.role === "doctor"
            ? storedUser
            : await loadUserProfile(storedUser);

        if (cancelled) return;

        setUser(resolvedUser);
        setPage(
          resolvedUser.role === "doctor"
            ? "doctor-dashboard"
            : "patient-dashboard"
        );
      }

      if (!cancelled) setInitializing(false);
    }

    initializeApp();

    return () => {
      cancelled = true;
    };
  }, []);

  function handlePatientLogin(
    loggedInUser
  ) {
    setUser(loggedInUser);
    setPage(
      "patient-dashboard"
    );
  }

  function handleDoctorLogin(
    loggedInUser
  ) {
    setUser(loggedInUser);
    setPage(
      "doctor-dashboard"
    );
  }

  function handleLogout() {
    clearAuth();
    setUser(null);
    setPage("home");
  }

  if (initializing) {
    return (
      <div className="app-loading">
        <div className="loading-logo">
          +
        </div>

        <div className="loading-spinner"></div>

        <span>
          Loading SmartCare...
        </span>
      </div>
    );
  }

  return (
    <>
      {page === "home" && (
        <HomePage
          onPatientLogin={() =>
            setPage(
              "patient-login"
            )
          }
          onDoctorLogin={() =>
            setPage(
              "doctor-login"
            )
          }
          onRegister={() =>
            setPage(
              "patient-register"
            )
          }
        />
      )}

      {page ===
        "patient-login" && (
        <PatientLoginPage
          onLogin={
            handlePatientLogin
          }
          onRegister={() =>
            setPage(
              "patient-register"
            )
          }
          onBack={() =>
            setPage("home")
          }
        />
      )}

      {page ===
        "patient-register" && (
        <PatientRegisterPage
          onRegistered={
            handlePatientLogin
          }
          onLogin={() =>
            setPage(
              "patient-login"
            )
          }
          onBack={() =>
            setPage("home")
          }
        />
      )}

      {page ===
        "doctor-login" && (
        <DoctorLoginPage
          onLogin={
            handleDoctorLogin
          }
          onBack={() =>
            setPage("home")
          }
        />
      )}

      {page ===
        "patient-dashboard" &&
        user?.role ===
          "patient" && (
          <PatientDashboard
            user={user}
            onLogout={
              handleLogout
            }
          />
        )}

      {page ===
        "doctor-dashboard" &&
        user?.role ===
          "doctor" && (
          <DoctorDashboard
            user={user}
            onLogout={
              handleLogout
            }
          />
        )}

      <style>
        {APP_STYLES}
      </style>
    </>
  );
}

/* =========================================================
   COMPLETE APPLICATION STYLES
   ========================================================= */

const APP_STYLES = `
* {
  box-sizing: border-box;
}

html {
  scroll-behavior: smooth;
}

body {
  margin: 0;
  font-family:
    Inter,
    ui-sans-serif,
    system-ui,
    -apple-system,
    BlinkMacSystemFont,
    "Segoe UI",
    sans-serif;

  background: #04111d;
  color: #f4fbff;
}

button,
input,
textarea,
select {
  font: inherit;
}

button {
  border: 0;
}

button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

a {
  color: inherit;
  text-decoration: none;
}

/* =========================================================
   BRAND
   ========================================================= */

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand-mark {
  width: 40px;
  height: 40px;
  border-radius: 12px;

  display: flex;
  align-items: center;
  justify-content: center;

  background:
    linear-gradient(
      135deg,
      #16d8e5,
      #167ce8
    );

  color: white;
  font-size: 25px;
  font-weight: 800;

  box-shadow:
    0 8px 25px
    rgba(19, 184, 225, 0.25);
}

.brand strong {
  display: block;
  color: #ffffff;
  font-size: 17px;
  line-height: 1;
}

.brand span {
  display: block;
  margin-top: 4px;

  color: #55778b;
  font-size: 7px;
  font-weight: 800;
  letter-spacing: 1.2px;
}

/* =========================================================
   PUBLIC NAVBAR
   ========================================================= */

.public-page {
  min-height: 100vh;
  background:
    radial-gradient(
      circle at 70% 20%,
      rgba(0, 191, 205, 0.08),
      transparent 30%
    ),
    #04111d;
}

.public-navbar {
  position: sticky;
  top: 0;
  z-index: 50;

  height: 76px;
  padding: 0 5%;

  display: flex;
  align-items: center;
  justify-content: space-between;

  border-bottom:
    1px solid
    rgba(102, 173, 200, 0.1);

  background:
    rgba(3, 15, 27, 0.92);

  backdrop-filter: blur(16px);
}

.public-nav {
  display: flex;
  gap: 32px;
  margin-left: auto;
  margin-right: 35px;
}

.public-nav a {
  color: #7895a5;
  font-size: 12px;
  font-weight: 700;
}

.public-nav a:hover {
  color: #32ded3;
}

.nav-actions {
  display: flex;
  gap: 8px;
}

.nav-login-button,
.nav-primary-button {
  padding: 10px 15px;
  border-radius: 9px;
  cursor: pointer;

  font-size: 11px;
  font-weight: 800;
}

.nav-login-button {
  background: rgba(30, 76, 102, 0.22);
  color: #a5c0cd;
}

.nav-primary-button {
  color: #04141f;
  background: #2adfd3;
}

/* =========================================================
   HERO
   ========================================================= */

.hero-section {
  position: relative;
  min-height: 650px;

  display: flex;
  align-items: center;

  padding:
    80px 8%
    100px;

  overflow: hidden;
}

.hero-grid {
  position: absolute;
  inset: 0;

  background-image:
    linear-gradient(
      rgba(47, 139, 171, 0.035) 1px,
      transparent 1px
    ),
    linear-gradient(
      90deg,
      rgba(47, 139, 171, 0.035) 1px,
      transparent 1px
    );

  background-size: 55px 55px;

  pointer-events: none;
}

.hero-content {
  position: relative;
  z-index: 2;
  max-width: 620px;
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;

  padding: 7px 11px;

  border:
    1px solid
    rgba(42, 223, 211, 0.18);

  border-radius: 100px;

  color: #4fe0d5;
  background:
    rgba(42, 223, 211, 0.05);

  font-size: 9px;
  font-weight: 900;
  letter-spacing: 1.2px;
}

.hero-badge span {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #2de0d2;
  box-shadow:
    0 0 10px
    rgba(45, 224, 210, 0.9);
}

.hero-content h1 {
  margin:
    25px 0
    15px;

  font-size:
    clamp(48px, 6vw, 82px);

  line-height: 0.98;
  letter-spacing: -4px;
}

.hero-content h1 span {
  color: #29ddd3;
}

.hero-content > p {
  max-width: 560px;

  color: #7897a8;
  font-size: 15px;
  line-height: 1.8;
}

.hero-buttons {
  display: flex;
  gap: 10px;
  margin-top: 30px;
}

.hero-primary,
.hero-secondary {
  padding: 13px 17px;
  border-radius: 9px;
  cursor: pointer;

  font-size: 11px;
  font-weight: 900;
}

.hero-primary {
  display: inline-flex;
  align-items: center;
  gap: 15px;

  color: #03131e;
  background: #2de0d2;
}

.hero-primary span {
  font-size: 16px;
}

.hero-secondary {
  color: #a8c1cc;
  background:
    rgba(40, 80, 103, 0.2);

  border:
    1px solid
    rgba(88, 142, 166, 0.18);
}

.hero-trust {
  display: flex;
  gap: 35px;
  margin-top: 55px;
}

.hero-trust div {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.hero-trust strong {
  color: #eafaff;
  font-size: 16px;
}

.hero-trust span {
  color: #56788b;
  font-size: 9px;
}

.hero-visual {
  position: absolute;
  right: 5%;
  width: 43%;
  height: 450px;

  display: flex;
  align-items: center;
  justify-content: center;
}

.ai-orbit {
  position: relative;
  width: 390px;
  height: 390px;
}

.orbit-ring {
  position: absolute;
  inset: 20px;

  border:
    1px solid
    rgba(42, 223, 211, 0.1);

  border-radius: 50%;
}

.orbit-two {
  inset: 65px;
  border-color:
    rgba(42, 161, 230, 0.13);
}

.hero-doctor-portrait-card {
  position: absolute;
  left: 50%;
  top: 50%;
  width: min(340px, 88%);
  overflow: hidden;
  transform: translate(-50%, -50%);
  border: 1px solid rgba(45, 224, 210, 0.28);
  border-radius: 24px;
  background: #061b2a;
  box-shadow: 0 28px 90px rgba(0, 0, 0, 0.42), 0 0 50px rgba(45, 224, 210, 0.07);
}

.hero-doctor-portrait {
  display: block;
  width: 100%;
  height: 350px;
  object-fit: cover;
  object-position: center 25%;
}

.hero-doctor-caption {
  position: relative;
  padding: 18px 22px 20px;
  background: linear-gradient(135deg, rgba(5, 25, 39, 0.98), rgba(4, 37, 49, 0.98));
}

.hero-doctor-eyebrow {
  display: block;
  color: #42dcd2;
  font-size: 8px;
  font-weight: 900;
  letter-spacing: 1.5px;
}

.hero-doctor-caption strong {
  display: block;
  margin-top: 8px;
  color: #f0fbff;
  font-size: 17px;
  line-height: 1.4;
}

.hero-doctor-online {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-top: 12px;
  color: #79a7b7;
  font-size: 10px;
}

.hero-doctor-online i {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #2de0d2;
  box-shadow: 0 0 10px rgba(45, 224, 210, 0.6);
}

.hero-ai-icon {
  width: 45px;
  height: 45px;

  display: flex;
  align-items: center;
  justify-content: center;

  border-radius: 13px;

  background:
    rgba(45, 224, 210, 0.1);

  color: #2de0d2;
  font-size: 22px;
}

.hero-ai-card > span {
  display: block;
  margin-top: 20px;

  color: #4e899d;
  font-size: 8px;
  font-weight: 900;
  letter-spacing: 1.3px;
}

.hero-ai-card > strong {
  display: block;
  margin-top: 8px;

  color: #eafaff;
  font-size: 17px;
  line-height: 1.4;
}

.hero-ai-status {
  margin-top: 20px;

  display: flex;
  align-items: center;
  gap: 6px;

  color: #5e8c9c;
  font-size: 9px;
}

.hero-ai-status span,
.online-dot,
.small-ai-status span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #2de0d2;
}

/* =========================================================
   PUBLIC SECTIONS
   ========================================================= */

.public-section {
  padding:
    100px 8%;
}

.section-alt {
  background:
    rgba(4, 18, 30, 0.75);
}

.section-heading {
  max-width: 700px;
  margin-bottom: 45px;
}

.section-label {
  display: block;

  color: #2de0d2;
  font-size: 9px;
  font-weight: 900;
  letter-spacing: 1.5px;
}

.section-heading h2 {
  margin:
    10px 0;

  color: #f3fbff;
  font-size: 38px;
  line-height: 1.1;
  letter-spacing: -1.5px;
}

.section-heading p {
  margin: 0;

  color: #67899a;
  font-size: 13px;
  line-height: 1.7;
}

/* =========================================================
   SERVICES
   ========================================================= */

.services-grid {
  display: grid;
  grid-template-columns:
    repeat(3, minmax(0, 1fr));

  gap: 15px;
}

.service-card {
  position: relative;

  padding: 25px;

  min-height: 190px;

  border:
    1px solid
    rgba(89, 148, 173, 0.13);

  border-radius: 15px;

  background:
    rgba(6, 25, 39, 0.65);

  transition: 0.2s ease;
}

.service-card:hover {
  transform: translateY(-3px);

  border-color:
    rgba(45, 224, 210, 0.25);
}

.service-icon {
  width: 38px;
  height: 38px;

  display: flex;
  align-items: center;
  justify-content: center;

  border-radius: 10px;

  color: #2de0d2;

  background:
    rgba(45, 224, 210, 0.08);

  font-size: 17px;
}

.service-card h3 {
  margin:
    18px 0 8px;

  color: #f2fbff;
  font-size: 15px;
}

.service-card p {
  margin: 0;

  color: #638495;
  font-size: 11px;
  line-height: 1.7;
}

.service-arrow {
  position: absolute;
  right: 22px;
  bottom: 20px;

  color: #2de0d2;
}

/* =========================================================
   SPECIALIZATIONS
   ========================================================= */

.specialization-grid {
  display: grid;
  grid-template-columns:
    repeat(4, minmax(0, 1fr));

  gap: 14px;
}

.specialization-card {
  padding: 20px;

  display: flex;
  gap: 14px;
  align-items: flex-start;

  border:
    1px solid
    rgba(89, 148, 173, 0.12);

  border-radius: 14px;

  background:
    rgba(6, 25, 39, 0.5);
}

.specialization-icon {
  min-width: 35px;
  width: 35px;
  height: 35px;

  display: flex;
  align-items: center;
  justify-content: center;

  border-radius: 9px;

  color: #2de0d2;
  background:
    rgba(45, 224, 210, 0.08);
}

.specialization-card h3 {
  margin: 0 0 5px;
  font-size: 13px;
}

.specialization-card p {
  margin: 0;
  color: #648596;
  font-size: 10px;
  line-height: 1.5;
}

/* =========================================================
   DOCTORS
   ========================================================= */

.doctor-grid {
  display: grid;
  grid-template-columns:
    repeat(3, minmax(0, 1fr));

  gap: 15px;
}

.doctor-card {
  padding: 22px;

  display: flex;
  gap: 15px;

  border:
    1px solid
    rgba(89, 148, 173, 0.13);

  border-radius: 15px;

  background:
    rgba(6, 25, 39, 0.65);
}

.doctor-avatar {
  min-width: 50px;
  width: 50px;
  height: 50px;

  display: flex;
  align-items: center;
  justify-content: center;

  border-radius: 14px;

  color: #2de0d2;
  background:
    rgba(45, 224, 210, 0.08);

  border:
    1px solid
    rgba(45, 224, 210, 0.12);

  font-size: 13px;
  font-weight: 900;
}

.doctor-card-content {
  min-width: 0;
  flex: 1;
}

.doctor-specialty {
  color: #2de0d2;
  font-size: 8px;
  font-weight: 900;
  letter-spacing: 1px;
  text-transform: uppercase;
}

.doctor-card h3 {
  margin:
    6px 0 5px;

  font-size: 15px;
}

.doctor-card p {
  margin: 0;

  color: #638596;
  font-size: 10px;
}

.doctor-meta {
  display: flex;
  gap: 12px;
  margin-top: 12px;
}

.doctor-meta span {
  color: #7694a2;
  font-size: 9px;
}

.doctor-fee {
  margin-top: 12px;

  color: #5c7d8d;
  font-size: 9px;
}

.doctor-fee strong {
  color: #c9f8f5;
}

/* =========================================================
   PUBLIC CTA
   ========================================================= */

.public-cta {
  margin:
    40px 8%
    80px;

  padding:
    50px;

  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 30px;

  border:
    1px solid
    rgba(45, 224, 210, 0.15);

  border-radius: 20px;

  background:
    linear-gradient(
      135deg,
      rgba(7, 39, 53, 0.9),
      rgba(5, 23, 37, 0.9)
    );
}

.public-cta h2 {
  margin:
    10px 0;

  font-size: 36px;
  line-height: 1.1;
}

.public-cta p {
  margin: 0;
  color: #678899;
  font-size: 12px;
}

.public-footer {
  min-height: 100px;

  padding:
    30px 8%;

  display: flex;
  align-items: center;
  justify-content: space-between;

  border-top:
    1px solid
    rgba(89, 148, 173, 0.1);
}

.public-footer p {
  color: #557586;
  font-size: 10px;
}

/* =========================================================
   AUTH
   ========================================================= */

.auth-page {
  min-height: 100vh;

  position: relative;
  overflow: hidden;

  background:
    radial-gradient(
      circle at 20% 30%,
      rgba(0, 205, 214, 0.07),
      transparent 30%
    ),
    #04111d;
}

.auth-background-grid {
  position: absolute;
  inset: 0;

  background-image:
    linear-gradient(
      rgba(47, 139, 171, 0.035) 1px,
      transparent 1px
    ),
    linear-gradient(
      90deg,
      rgba(47, 139, 171, 0.035) 1px,
      transparent 1px
    );

  background-size: 55px 55px;
}

.auth-topbar {
  position: relative;
  z-index: 2;

  height: 80px;
  padding:
    0 5%;

  display: flex;
  align-items: center;
  justify-content: space-between;

  border-bottom:
    1px solid
    rgba(89, 148, 173, 0.1);
}

.back-button {
  padding: 9px 12px;

  border-radius: 8px;

  background:
    rgba(28, 71, 95, 0.2);

  color: #7e9bab;

  cursor: pointer;

  font-size: 10px;
  font-weight: 700;
}

.auth-container {
  position: relative;
  z-index: 2;

  max-width: 1000px;

  margin:
    70px auto;

  padding: 0 25px;

  display: grid;
  grid-template-columns:
    1fr 420px;

  gap: 70px;

  align-items: center;
}

.auth-intro h1 {
  margin:
    20px 0 15px;

  font-size: 55px;
  line-height: 1;
  letter-spacing: -2px;
}

.auth-intro > p {
  max-width: 470px;

  color: #6c8a9a;
  line-height: 1.8;
  font-size: 13px;
}

.auth-feature-list {
  display: flex;
  flex-direction: column;
  gap: 13px;

  margin-top: 35px;
}

.auth-feature-list div {
  color: #7594a3;
  font-size: 11px;
}

.auth-feature-list span {
  color: #2de0d2;
  margin-right: 8px;
}

.auth-card {
  padding: 30px;

  border:
    1px solid
    rgba(89, 148, 173, 0.16);

  border-radius: 18px;

  background:
    rgba(6, 24, 38, 0.86);

  box-shadow:
    0 30px 80px
    rgba(0, 0, 0, 0.25);
}

.auth-card-header h2 {
  margin:
    9px 0 5px;

  font-size: 25px;
}

.auth-card-header p {
  margin: 0 0 25px;

  color: #658596;
  font-size: 11px;
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.auth-form label {
  display: flex;
  flex-direction: column;
  gap: 7px;

  color: #91abb8;
  font-size: 10px;
  font-weight: 700;
}

.auth-form input {
  width: 100%;

  padding: 12px 13px;

  border:
    1px solid
    rgba(89, 148, 173, 0.17);

  border-radius: 8px;

  outline: none;

  background:
    rgba(2, 14, 24, 0.8);

  color: white;

  font-size: 11px;
}

.auth-form input:focus {
  border-color:
    rgba(45, 224, 210, 0.5);

  box-shadow:
    0 0 0 3px
    rgba(45, 224, 210, 0.05);
}

.form-two-columns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.auth-submit {
  margin-top: 5px;

  padding: 13px;

  border-radius: 8px;

  color: #03131e;
  background: #2de0d2;

  cursor: pointer;

  font-size: 11px;
  font-weight: 900;
}

.auth-switch {
  margin-top: 20px;

  display: flex;
  justify-content: center;
  gap: 5px;

  color: #607f8e;
  font-size: 10px;
}

.auth-switch button {
  color: #2de0d2;
  background: transparent;
  cursor: pointer;
  font-weight: 800;
}

.error-message {
  margin-bottom: 15px;
  padding: 11px 13px;

  border:
    1px solid
    rgba(255, 92, 107, 0.2);

  border-radius: 8px;

  color: #ff9da7;

  background:
    rgba(255, 92, 107, 0.06);

  font-size: 10px;
  line-height: 1.5;
}

/* =========================================================
   DASHBOARD
   ========================================================= */

.dashboard-page {
  min-height: 100vh;
  background:
    radial-gradient(
      circle at 80% 10%,
      rgba(0, 198, 209, 0.045),
      transparent 25%
    ),
    #04111d;
}

.dashboard-topbar {
  position: sticky;
  top: 0;
  z-index: 40;

  height: 64px;

  padding:
    0 20px;

  display: flex;
  align-items: center;
  justify-content: space-between;

  border-bottom:
    1px solid
    rgba(89, 148, 173, 0.1);

  background:
    rgba(3, 15, 27, 0.94);

  backdrop-filter: blur(14px);
}

.dashboard-user {
  display: flex;
  align-items: center;
  gap: 9px;
}

.online-status {
  display: flex;
  align-items: center;
  gap: 5px;

  color: #45dcd3;
  font-size: 9px;
  font-weight: 800;
}

.online-status span {
  width: 5px;
  height: 5px;
  border-radius: 50%;

  background: #2de0d2;
  box-shadow:
    0 0 8px
    rgba(45, 224, 210, 0.8);
}

.user-avatar {
  width: 30px;
  height: 30px;

  display: flex;
  align-items: center;
  justify-content: center;

  border-radius: 8px;

  color: white;
  background:
    linear-gradient(
      135deg,
      #18cbd8,
      #1679dc
    );

  font-size: 9px;
  font-weight: 900;
}

.user-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.user-info strong {
  color: #e9f8fc;
  font-size: 10px;
}

.user-info span {
  color: #54798b;
  font-size: 7px;
  font-weight: 800;
}

.logout-button {
  margin-left: 10px;

  padding: 7px 11px;

  border-radius: 7px;

  background:
    rgba(28, 67, 90, 0.22);

  color: #7e9baa;

  cursor: pointer;

  font-size: 9px;
  font-weight: 700;
}

.dashboard-shell {
  display: grid;
  grid-template-columns: 215px 1fr;
  min-height: calc(100vh - 64px);
}

.dashboard-sidebar {
  padding: 25px 13px;

  border-right:
    1px solid
    rgba(89, 148, 173, 0.1);

  background:
    rgba(3, 16, 27, 0.65);
}

.sidebar-welcome {
  padding:
    0 10px
    22px;

  border-bottom:
    1px solid
    rgba(89, 148, 173, 0.08);
}

.sidebar-welcome span {
  color: #4f899a;
  font-size: 7px;
  font-weight: 900;
  letter-spacing: 1.1px;
}

.sidebar-welcome strong {
  display: block;

  margin-top: 8px;

  color: #e7f6fb;

  font-size: 15px;
  line-height: 1.4;
}

.dashboard-nav {
  display: flex;
  flex-direction: column;
  gap: 3px;

  margin-top: 17px;
}

.dashboard-nav-button {
  width: 100%;

  padding: 10px;

  display: flex;
  align-items: center;
  gap: 9px;

  border-radius: 8px;

  color: #5f7f8e;
  background: transparent;

  text-align: left;

  cursor: pointer;

  font-size: 9px;
  font-weight: 700;
}

.dashboard-nav-button:hover,
.dashboard-nav-button.active {
  color: #d9fbfa;
  background:
    rgba(45, 224, 210, 0.07);
}

.dashboard-nav-button.active {
  box-shadow:
    inset 2px 0 #2de0d2;
}

.dashboard-nav-icon {
  width: 20px;
  text-align: center;
  color: #2de0d2;
}

.sidebar-ai-card {
  margin-top: 35px;
  padding: 15px;

  border:
    1px solid
    rgba(45, 224, 210, 0.11);

  border-radius: 12px;

  background:
    rgba(45, 224, 210, 0.035);
}

.sidebar-ai-icon {
  color: #2de0d2;
  font-size: 16px;
}

.sidebar-ai-card strong {
  display: block;
  margin-top: 7px;

  font-size: 11px;
}

.sidebar-ai-card p {
  color: #55798a;
  font-size: 8px;
  line-height: 1.6;
}

.sidebar-ai-card button {
  color: #2de0d2;
  background: transparent;
  cursor: pointer;

  font-size: 8px;
  font-weight: 900;
}

.dashboard-main {
  min-width: 0;
  padding: 30px;
  max-width: 1400px;
}

.dashboard-heading {
  margin-bottom: 25px;

  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
}

.dashboard-heading h1 {
  margin:
    7px 0 5px;

  font-size: 32px;
  letter-spacing: -1.3px;
}

.dashboard-heading h1 span {
  color: #2de0d2;
}

.dashboard-heading p {
  margin: 0;
  color: #5d7d8c;
  font-size: 10px;
}

.dashboard-ai-button,
.refresh-button {
  padding: 10px 13px;

  border-radius: 8px;

  background:
    rgba(45, 224, 210, 0.08);

  border:
    1px solid
    rgba(45, 224, 210, 0.14);

  color: #45ddd4;

  cursor: pointer;

  font-size: 9px;
  font-weight: 900;
}

/* =========================================================
   DASHBOARD CARDS
   ========================================================= */

.dashboard-card {
  padding: 20px;

  border:
    1px solid
    rgba(89, 148, 173, 0.11);

  border-radius: 14px;

  background:
    rgba(6, 24, 38, 0.62);
}

.card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 15px;

  margin-bottom: 20px;
}

.card-header h2 {
  margin:
    7px 0 0;

  font-size: 16px;
}

.card-description {
  color: #638596;
  font-size: 10px;
  line-height: 1.7;
}

.text-button {
  color: #2de0d2;
  background: transparent;
  cursor: pointer;

  font-size: 9px;
  font-weight: 800;
}

.overview-stat-grid {
  display: grid;
  grid-template-columns:
    repeat(3, minmax(0, 1fr));

  gap: 12px;

  margin-bottom: 15px;
}

.stat-card {
  padding: 16px;

  display: flex;
  align-items: center;
  gap: 12px;

  border:
    1px solid
    rgba(89, 148, 173, 0.11);

  border-radius: 12px;

  background:
    rgba(6, 24, 38, 0.55);
}

.stat-icon {
  width: 35px;
  height: 35px;

  display: flex;
  align-items: center;
  justify-content: center;

  border-radius: 9px;

  color: #2de0d2;
  background:
    rgba(45, 224, 210, 0.08);
}

.stat-card strong {
  display: block;
  color: #f2fbff;
  font-size: 18px;
}

.stat-card span {
  display: block;
  margin-top: 3px;
  color: #5b7c8c;
  font-size: 8px;
}

.overview-grid {
  display: grid;
  grid-template-columns:
    1.3fr 1fr;

  gap: 15px;

  margin-bottom: 15px;
}

.small-ai-status {
  display: flex;
  align-items: center;
  gap: 5px;

  color: #4cd9d0;
  font-size: 8px;
}

.large-ai-button {
  width: 100%;

  margin-top: 18px;
  padding: 13px;

  display: flex;
  align-items: center;
  gap: 10px;

  border-radius: 9px;

  color: #4edfd6;

  background:
    rgba(45, 224, 210, 0.07);

  border:
    1px solid
    rgba(45, 224, 210, 0.13);

  cursor: pointer;

  font-size: 10px;
  font-weight: 800;
  text-align: left;
}

.large-ai-button span {
  font-size: 16px;
}

.large-ai-button strong {
  margin-left: auto;
}

/* =========================================================
   APPOINTMENT PREVIEW
   ========================================================= */

.appointment-preview {
  display: flex;
  align-items: center;
  gap: 13px;

  padding: 12px;

  border-radius: 10px;

  background:
    rgba(2, 15, 26, 0.6);
}

.appointment-date-box {
  min-width: 48px;
  width: 48px;
  padding: 8px;

  display: flex;
  flex-direction: column;
  align-items: center;

  border-radius: 9px;

  background:
    rgba(45, 224, 210, 0.08);
}

.appointment-date-box span {
  color: #2de0d2;
  font-size: 7px;
  font-weight: 900;
  text-transform: uppercase;
}

.appointment-date-box strong {
  margin-top: 2px;
  font-size: 17px;
}

.appointment-preview-info {
  flex: 1;
}

.appointment-specialty {
  color: #2de0d2;
  font-size: 8px;
  font-weight: 800;
}

.appointment-preview-info h3 {
  margin:
    3px 0;

  font-size: 12px;
}

.appointment-preview-info p {
  margin: 0;

  color: #7693a1;
  font-size: 9px;
}

/* =========================================================
   STATUS
   ========================================================= */

.status-badge {
  display: inline-flex;
  padding: 5px 8px;

  border-radius: 6px;

  font-size: 7px;
  font-weight: 900;
  letter-spacing: 0.5px;
}

.status-scheduled {
  color: #4fe0d6;
  background:
    rgba(45, 224, 210, 0.08);
}

.status-rescheduled {
  color: #e2c46e;
  background:
    rgba(226, 196, 110, 0.08);
}

.status-cancelled {
  color: #ff8e9b;
  background:
    rgba(255, 95, 111, 0.08);
}

.status-completed {
  color: #86c8ff;
  background:
    rgba(94, 172, 255, 0.08);
}

/* =========================================================
   MINI SERVICES
   ========================================================= */

.services-preview-card {
  margin-bottom: 15px;
}

.mini-services-grid {
  display: grid;
  grid-template-columns:
    repeat(4, minmax(0, 1fr));

  gap: 10px;
}

.mini-service {
  padding: 12px;

  display: flex;
  gap: 9px;

  border:
    1px solid
    rgba(89, 148, 173, 0.08);

  border-radius: 9px;
}

.mini-service-icon {
  color: #2de0d2;
}

.mini-service strong {
  display: block;
  font-size: 9px;
}

.mini-service span {
  display: block;
  margin-top: 4px;

  color: #587888;
  font-size: 7px;
  line-height: 1.5;
}

/* =========================================================
   APPOINTMENT LIST
   ========================================================= */

.appointment-list {
  display: flex;
  flex-direction: column;
}

.appointment-row {
  padding:
    13px 0;

  display: grid;
  grid-template-columns:
    150px
    1.1fr
    1fr
    90px;

  gap: 15px;
  align-items: center;

  border-bottom:
    1px solid
    rgba(89, 148, 173, 0.08);
}

.appointment-row:last-child {
  border-bottom: 0;
}

.appointment-row-date {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.appointment-row-date strong {
  color: #e8f7fc;
  font-size: 10px;
}

.appointment-row-date span {
  color: #2de0d2;
  font-size: 9px;
  font-weight: 800;
}

.appointment-row-doctor {
  display: flex;
  align-items: center;
  gap: 9px;
}

.table-avatar {
  width: 30px;
  height: 30px;

  display: flex;
  align-items: center;
  justify-content: center;

  border-radius: 8px;

  color: #2de0d2;
  background:
    rgba(45, 224, 210, 0.08);

  font-size: 8px;
  font-weight: 900;
}

.appointment-row-doctor strong {
  display: block;
  font-size: 10px;
}

.appointment-row-doctor span {
  display: block;
  margin-top: 3px;

  color: #557789;
  font-size: 8px;
}

.appointment-row-reason span {
  color: #4d7182;
  font-size: 7px;
  text-transform: uppercase;
}

.appointment-row-reason p {
  margin: 4px 0 0;

  color: #8ba4b1;
  font-size: 8px;
}

/* =========================================================
   SERVICES / DOCTORS DASHBOARD
   ========================================================= */

.dashboard-services {
  grid-template-columns:
    repeat(3, minmax(0, 1fr));
}

.dashboard-doctor-grid {
  grid-template-columns:
    repeat(2, minmax(0, 1fr));
}

.specialization-filter {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin-bottom: 18px;
}

.filter-button {
  padding: 8px 11px;

  border-radius: 7px;

  color: #668594;

  background:
    rgba(28, 65, 87, 0.18);

  border:
    1px solid
    rgba(89, 148, 173, 0.09);

  cursor: pointer;

  font-size: 8px;
  font-weight: 800;
}

.filter-button.active {
  color: #03131e;
  background: #2de0d2;
  border-color: #2de0d2;
}

/* =========================================================
   AI CHAT
   ========================================================= */

.ai-status-pill {
  display: flex;
  align-items: center;
  gap: 6px;

  padding: 8px 11px;

  border-radius: 7px;

  color: #54dcd4;

  background:
    rgba(45, 224, 210, 0.05);

  border:
    1px solid
    rgba(45, 224, 210, 0.1);

  font-size: 8px;
  font-weight: 800;
}

.ai-status-pill span {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #2de0d2;
}

.ai-chat-layout {
  display: grid;
  grid-template-columns:
    minmax(0, 1fr)
    225px;

  gap: 14px;

  align-items: start;
}

.chat-card {
  min-width: 0;

  border:
    1px solid
    rgba(89, 148, 173, 0.13);

  border-radius: 15px;

  background:
    rgba(5, 21, 34, 0.75);

  overflow: hidden;
}

.chat-header {
  height: 64px;

  padding:
    0 15px;

  display: flex;
  align-items: center;
  gap: 10px;

  border-bottom:
    1px solid
    rgba(89, 148, 173, 0.08);
}

.ai-icon,
.message-ai-icon {
  width: 29px;
  height: 29px;

  display: flex;
  align-items: center;
  justify-content: center;

  border-radius: 8px;

  color: #03131e;
  background: #2de0d2;

  font-weight: 900;
}

.message-ai-icon {
  min-width: 24px;
  width: 24px;
  height: 24px;
  font-size: 10px;
}

.chat-header-text {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.chat-header-text strong {
  font-size: 10px;
}

.chat-header-text span {
  color: #567788;
  font-size: 7px;
}

.online-dot {
  margin-left: auto;
}

.chat-messages {
  min-height: 480px;
  max-height: 600px;

  padding: 18px;

  overflow-y: auto;

  display: flex;
  flex-direction: column;
  gap: 14px;
}

.chat-message {
  max-width: 100%;
}

.chat-message-user {
  display: flex;
  justify-content: flex-end;
}

.chat-message-user .message-bubble {
  max-width: 75%;

  padding: 10px 13px;

  border-radius:
    12px 12px 3px 12px;

  color: #c8f5f3;

  background:
    rgba(34, 135, 139, 0.19);

  border:
    1px solid
    rgba(45, 224, 210, 0.1);

  font-size: 9px;
  line-height: 1.6;
  white-space: pre-wrap;
}

.chat-message-ai .message-bubble {
  max-width: 85%;

  display: flex;
  align-items: flex-start;
  gap: 7px;
}

.message-content {
  padding:
    10px 12px;

  border:
    1px solid
    rgba(89, 148, 173, 0.1);

  border-radius:
    3px 12px 12px 12px;

  color: #a5bfca;

  background:
    rgba(10, 31, 46, 0.85);

  font-size: 9px;
  line-height: 1.6;
  white-space: pre-wrap;
}

/* =========================================================
   CHAT BOOKING OPTIONS
   ========================================================= */

.chat-booking-options {
  width: calc(100% - 31px);

  margin:
    10px 0
    0 31px;

  padding: 13px;

  border:
    1px solid
    rgba(42, 224, 211, 0.14);

  border-radius: 13px;

  background:
    rgba(5, 22, 35, 0.72);
}

.chat-booking-title {
  display: flex;
  align-items: center;
  justify-content: space-between;

  gap: 10px;

  margin-bottom: 10px;
}

.chat-booking-title > div {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.chat-booking-title span {
  color: #27e0d2;
  font-size: 7px;
  font-weight: 900;
  letter-spacing: 1.1px;
}

.chat-booking-title strong {
  color: #ffffff;
  font-size: 11px;
}

.chat-booking-title small {
  color: #5fded4;

  background:
    rgba(39, 224, 210, 0.07);

  border:
    1px solid
    rgba(39, 224, 210, 0.12);

  padding: 5px 7px;

  border-radius: 6px;

  white-space: nowrap;

  font-size: 7px;
}

.chat-slot-grid {
  display: grid;
  grid-template-columns:
    repeat(2, minmax(0, 1fr));

  gap: 8px;
}

.chat-slot-card {
  position: relative;

  padding: 11px;

  border:
    1px solid
    rgba(112, 161, 188, 0.13);

  border-radius: 10px;

  background:
    rgba(3, 15, 26, 0.86);

  transition: 0.2s ease;
}

.chat-slot-card:hover {
  border-color:
    rgba(39, 224, 210, 0.4);

  transform:
    translateY(-1px);
}

.chat-slot-selected {
  border-color: #27e0d2;

  background:
    rgba(39, 224, 210, 0.07);

  box-shadow:
    0 0 0 1px
    rgba(39, 224, 210, 0.15);
}

.chat-slot-top {
  display: flex;
  align-items: center;
  justify-content: space-between;

  margin-bottom: 7px;
}

.slot-period {
  color: #5dded4;
  font-size: 7px;
  font-weight: 900;
  letter-spacing: 1px;
}

.slot-selected-badge {
  color: #27e0d2;
  font-size: 7px;
  font-weight: 900;
}

.chat-slot-doctor {
  color: #ffffff;
  font-size: 10px;
  font-weight: 900;
}

.chat-slot-department {
  margin-top: 3px;

  color: #22d6ea;
  font-size: 8px;
  font-weight: 800;
}

.chat-slot-date {
  margin-top: 8px;

  color: #7897a6;
  font-size: 8px;
}

.chat-slot-time {
  margin-top: 3px;

  color: #2de0d2;
  font-size: 14px;
  font-weight: 900;
}

.chat-slot-fee {
  margin-top: 4px;

  color: #91aab6;
  font-size: 8px;
}

.chat-slot-button {
  width: 100%;

  margin-top: 9px;
  padding: 7px;

  border:
    1px solid
    rgba(39, 224, 210, 0.18);

  border-radius: 6px;

  background:
    rgba(39, 224, 210, 0.05);

  color: #6be5dc;

  cursor: pointer;

  font-size: 7px;
  font-weight: 900;
}

.chat-slot-button:hover {
  background:
    rgba(39, 224, 210, 0.12);
}

.chat-slot-button.selected {
  color: #03131e;
  background: #27e0d2;
  border-color: #27e0d2;
}

/* =========================================================
   BOOKING CONFIRM
   ========================================================= */

.booking-confirm-panel {
  margin-top: 10px;
  padding: 10px;

  display: flex;
  align-items: center;
  justify-content: space-between;

  gap: 10px;

  border:
    1px solid
    rgba(39, 224, 210, 0.24);

  border-radius: 9px;

  background:
    rgba(39, 224, 210, 0.05);
}

.booking-confirm-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.booking-confirm-icon {
  width: 28px;
  height: 28px;

  display: flex;
  align-items: center;
  justify-content: center;

  border-radius: 7px;

  color: #2de0d2;
  background:
    rgba(39, 224, 210, 0.1);

  font-size: 12px;
  font-weight: 900;
}

.booking-confirm-info > div:last-child {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.booking-confirm-info span {
  color: #598394;
  font-size: 6px;
  font-weight: 800;
  letter-spacing: 0.8px;
}

.booking-confirm-info strong {
  color: #ffffff;
  font-size: 9px;
}

.booking-confirm-info small {
  color: #8ba3af;
  font-size: 7px;
}

.booking-confirm-actions {
  display: flex;
  gap: 5px;
}

.button {
  padding: 8px 10px;

  border-radius: 6px;

  cursor: pointer;

  font-size: 7px;
  font-weight: 900;
}

.button-primary {
  color: #03131e;
  background: #2de0d2;
}

.button-ghost {
  color: #8da6b3;
  background:
    rgba(35, 71, 91, 0.3);
}

/* =========================================================
   CHAT QUICK ACTIONS
   ========================================================= */

.chat-quick-actions {
  padding:
    9px 13px;

  display: flex;
  gap: 6px;

  border-top:
    1px solid
    rgba(89, 148, 173, 0.08);
}

.chat-quick-actions button {
  padding: 7px 9px;

  border-radius: 6px;

  color: #7395a5;

  background:
    rgba(29, 63, 82, 0.25);

  cursor: pointer;

  font-size: 7px;
  font-weight: 700;
}

.chat-quick-actions button:hover {
  color: #b8f6f1;
  background:
    rgba(45, 224, 210, 0.07);
}


/* Feature-rich quick prompts for symptoms, home care and hospital workflows */
.careflow-chat-layout .chat-quick-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 9px;
  padding: 14px 18px;
  background: linear-gradient(180deg, rgba(7, 29, 43, .82), rgba(4, 20, 31, .94));
  border-top: 1px solid rgba(77, 196, 205, .12);
}

.careflow-chat-layout .chat-quick-actions button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-height: 38px;
  padding: 9px 13px;
  border: 1px solid rgba(103, 176, 197, .18);
  border-radius: 999px;
  color: #b7d4e2;
  background: rgba(12, 43, 59, .78);
  font-size: 11px;
  font-weight: 750;
  letter-spacing: .01em;
  white-space: nowrap;
  transition: transform .2s ease, border-color .2s ease, background .2s ease, box-shadow .2s ease, color .2s ease;
}

.careflow-chat-layout .chat-quick-actions button span {
  color: #35e0d1;
  font-size: 14px;
}

.careflow-chat-layout .chat-quick-actions button:hover,
.careflow-chat-layout .chat-quick-actions button:focus-visible {
  transform: translateY(-2px);
  color: #f4ffff;
  border-color: rgba(45, 224, 210, .62);
  background: linear-gradient(135deg, rgba(22, 113, 127, .45), rgba(15, 52, 76, .92));
  box-shadow: 0 8px 22px rgba(0, 205, 204, .11);
  outline: none;
}

.careflow-chat-layout .chat-quick-actions button:focus-visible {
  outline: 2px solid #35e0d1;
  outline-offset: 3px;
}

@media (max-width: 720px) {
  .careflow-chat-layout .chat-quick-actions {
    flex-wrap: nowrap;
    overflow-x: auto;
    padding: 10px 12px;
    scrollbar-width: thin;
  }
  .careflow-chat-layout .chat-quick-actions button {
    flex: 0 0 auto;
    min-height: 36px;
    padding: 8px 11px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .careflow-chat-layout .chat-quick-actions button {
    transition: none;
  }
  .careflow-chat-layout .chat-quick-actions button:hover {
    transform: none;
  }
}

/* =========================================================
   CHAT INPUT
   ========================================================= */

.chat-input-area {
  padding:
    10px 13px;

  display: flex;
  gap: 8px;

  border-top:
    1px solid
    rgba(89, 148, 173, 0.08);
}

.chat-input-area input {
  flex: 1;

  min-width: 0;

  padding: 11px;

  border:
    1px solid
    rgba(89, 148, 173, 0.13);

  border-radius: 8px;

  outline: none;

  background:
    rgba(3, 15, 26, 0.8);

  color: #dffaff;

  font-size: 9px;
}

.chat-input-area input:focus {
  border-color:
    rgba(45, 224, 210, 0.35);
}

.chat-send-button {
  width: 38px;

  border-radius: 8px;

  color: #03131e;
  background: #2de0d2;

  cursor: pointer;

  font-size: 17px;
}

.chat-disclaimer {
  padding:
    0 13px
    11px;

  color: #385a6b;
  font-size: 6px;
  line-height: 1.5;
}

/* =========================================================
   TYPING
   ========================================================= */

.typing-indicator {
  padding:
    11px 12px;

  display: flex;
  gap: 4px;

  border-radius:
    3px 12px 12px 12px;

  background:
    rgba(10, 31, 46, 0.85);
}

.typing-indicator span {
  width: 4px;
  height: 4px;

  border-radius: 50%;

  background: #2de0d2;

  animation:
    careflowTyping
    1.2s infinite
    ease-in-out;
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.15s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes careflowTyping {
  0%,
  60%,
  100% {
    opacity: 0.3;
    transform: translateY(0);
  }

  30% {
    opacity: 1;
    transform: translateY(-3px);
  }
}

/* =========================================================
   AI SIDEBAR
   ========================================================= */

.ai-sidebar {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ai-sidebar-card {
  padding: 14px;

  border:
    1px solid
    rgba(89, 148, 173, 0.1);

  border-radius: 13px;

  background:
    rgba(5, 22, 35, 0.65);
}

.ai-sidebar-header {
  display: flex;
  flex-direction: column;
  gap: 3px;

  margin-bottom: 13px;
}

.ai-sidebar-header span {
  color: #2de0d2;
  font-size: 7px;
  font-weight: 900;
  letter-spacing: 1px;
}

.ai-sidebar-header strong {
  color: #dcecf1;
  font-size: 11px;
}

.workflow-step {
  padding: 8px 0;

  display: grid;
  grid-template-columns:
    25px 1fr 15px;

  gap: 6px;
  align-items: center;

  border-bottom:
    1px solid
    rgba(89, 148, 173, 0.06);
}

.workflow-step:last-child {
  border-bottom: 0;
}

.workflow-step > div:first-child {
  width: 22px;
  height: 22px;

  display: flex;
  align-items: center;
  justify-content: center;

  border-radius: 6px;

  color: #527687;
  background:
    rgba(32, 69, 88, 0.25);

  font-size: 6px;
  font-weight: 900;
}

.workflow-step.active
  > div:first-child {
  color: #2de0d2;
  background:
    rgba(45, 224, 210, 0.08);
}

.workflow-step > div:nth-child(2) {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.workflow-step strong {
  color: #9ab7c4;
  font-size: 8px;
}

.workflow-step span {
  color: #47697a;
  font-size: 6px;
}

.workflow-step > span:last-child {
  color: #3c697a;
  font-size: 8px;
}

.workflow-step.active
  > span:last-child {
  color: #2de0d2;
}

.knowledge-item {
  padding: 8px 0;

  display: flex;
  gap: 7px;

  color: #648696;

  font-size: 7px;
}

.knowledge-item span {
  color: #2de0d2;
  font-size: 6px;
}

/* =========================================================
   DOCTOR DASHBOARD
   ========================================================= */

.doctor-dashboard-shell {
  max-width: 1500px;
  padding: 30px;
}

.table-count {
  padding: 6px 9px;

  border-radius: 6px;

  color: #58dcd3;
  background:
    rgba(45, 224, 210, 0.06);

  font-size: 7px;
  font-weight: 800;
}

.doctor-table-wrapper {
  width: 100%;
  overflow-x: auto;
}

.doctor-table {
  width: 100%;
  border-collapse: collapse;
}

.doctor-table th {
  padding:
    10px 8px;

  color: #4d7181;

  border-bottom:
    1px solid
    rgba(89, 148, 173, 0.1);

  text-align: left;

  font-size: 7px;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.doctor-table td {
  padding:
    12px 8px;

  border-bottom:
    1px solid
    rgba(89, 148, 173, 0.06);

  vertical-align: middle;
}

.appointment-id {
  color: #5e8b9d;
  font-size: 8px;
}

.patient-table-person {
  display: flex;
  align-items: center;
  gap: 8px;
}

.patient-table-person strong {
  display: block;
  color: #dceef3;
  font-size: 9px;
}

.patient-table-person span {
  display: block;
  margin-top: 3px;
  color: #527384;
  font-size: 7px;
}

.contact-cell,
.date-time-cell {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.contact-cell span {
  color: #7c99a7;
  font-size: 7px;
}

.date-time-cell strong {
  color: #d9eef4;
  font-size: 8px;
}

.date-time-cell span {
  color: #2de0d2;
  font-size: 8px;
  font-weight: 800;
}

.reason-cell {
  display: block;
  max-width: 160px;

  color: #7895a2;

  font-size: 7px;
  line-height: 1.5;
}

/* =========================================================
   LOADING / EMPTY
   ========================================================= */

.loading-box {
  min-height: 180px;

  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;

  gap: 10px;

  color: #5b7c8c;
  font-size: 9px;
}

.loading-spinner {
  width: 24px;
  height: 24px;

  border:
    2px solid
    rgba(45, 224, 210, 0.12);

  border-top-color: #2de0d2;

  border-radius: 50%;

  animation:
    careflowSpin
    0.8s linear
    infinite;
}

@keyframes careflowSpin {
  to {
    transform: rotate(360deg);
  }
}

.empty-state {
  min-height: 190px;

  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;

  text-align: center;
}

.empty-icon {
  width: 38px;
  height: 38px;

  display: flex;
  align-items: center;
  justify-content: center;

  border-radius: 10px;

  color: #2de0d2;
  background:
    rgba(45, 224, 210, 0.07);

  font-size: 15px;
}

.empty-state h3 {
  margin:
    12px 0 5px;

  font-size: 12px;
}

.empty-state p {
  max-width: 330px;

  margin: 0;

  color: #567788;

  font-size: 8px;
  line-height: 1.6;
}

/* =========================================================
   APP LOADING
   ========================================================= */

.app-loading {
  min-height: 100vh;

  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;

  gap: 13px;

  background: #04111d;
  color: #648696;

  font-size: 9px;
}

.loading-logo {
  width: 45px;
  height: 45px;

  display: flex;
  align-items: center;
  justify-content: center;

  border-radius: 13px;

  color: white;

  background:
    linear-gradient(
      135deg,
      #16d8e5,
      #167ce8
    );

  font-size: 26px;
  font-weight: 900;
}

/* =========================================================
   RESPONSIVE
   ========================================================= */


/* =========================================================
   DOCTOR PORTAL — ANALYTICS, SCHEDULING AND PROFILE POLISH
   ========================================================= */
.doctor-dashboard-shell { width: 100%; max-width: 1600px; margin: 0 auto; padding: 30px clamp(18px, 3vw, 48px) 48px; }
.doctor-welcome-panel { position: relative; display: flex; align-items: center; justify-content: space-between; gap: 24px; min-height: 190px; padding: 30px 32px; margin-bottom: 22px; overflow: hidden; border: 1px solid rgba(45,224,210,.15); border-radius: 22px; background: radial-gradient(ellipse at 88% 12%, rgba(26,170,187,.16), transparent 36%), linear-gradient(135deg, rgba(8,34,49,.96), rgba(4,18,30,.98)); }
.doctor-welcome-panel:after { content:""; position:absolute; inset:0; pointer-events:none; opacity:.32; background-image:linear-gradient(rgba(47,139,171,.04) 1px,transparent 1px),linear-gradient(90deg,rgba(47,139,171,.04) 1px,transparent 1px); background-size:28px 28px; }
.doctor-welcome-copy { position:relative; z-index:1; }
.doctor-welcome-copy h1 { margin:10px 0 8px; font-size:clamp(30px,4vw,46px); letter-spacing:-1.8px; }
.doctor-welcome-copy h1 span { color:#2de0d2; }
.doctor-welcome-copy p { margin:0; color:#7d9caf; font-size:13px; line-height:1.7; }
.doctor-welcome-tags { display:flex; flex-wrap:wrap; gap:9px; margin-top:18px; }
.doctor-welcome-tags span { padding:7px 10px; border:1px solid rgba(45,224,210,.12); border-radius:99px; color:#8eb3bf; background:rgba(45,224,210,.045); font-size:10px; }
.doctor-welcome-avatar { position:relative; z-index:1; display:grid; place-items:center; flex:0 0 104px; width:104px; height:104px; border-radius:30px; color:#041520; background:linear-gradient(140deg,#35e5d6,#158cce); box-shadow:0 12px 42px rgba(17,191,205,.15); font-size:27px; font-weight:900; }
.doctor-welcome-avatar i { position:absolute; right:-5px; bottom:-5px; display:grid; place-items:center; width:27px; height:27px; border:4px solid #071722; border-radius:50%; color:#041520; background:#43e4b1; font-size:12px; font-style:normal; }
.doctor-refresh { position:relative; z-index:1; align-self:flex-start; }
.doctor-dashboard-tabs { display:flex; gap:7px; margin:0 0 22px; padding:5px; width:max-content; max-width:100%; border:1px solid rgba(89,148,173,.12); border-radius:13px; background:rgba(5,22,35,.8); }
.doctor-dashboard-tabs button { padding:11px 16px; border-radius:9px; color:#7c9aaa; background:transparent; cursor:pointer; font-size:12px; font-weight:800; white-space:nowrap; }
.doctor-dashboard-tabs button.active { color:#04151f; background:#2de0d2; box-shadow:0 5px 20px rgba(45,224,210,.12); }
.doctor-stat-grid { grid-template-columns:repeat(4,minmax(0,1fr)); gap:14px; margin-bottom:20px; }
.doctor-stat-grid .stat-card { min-width:0; border-radius:17px; padding:20px; background:linear-gradient(145deg,rgba(7,29,43,.96),rgba(5,21,33,.94)); }
.doctor-stat-grid .stat-card strong { font-size:25px; }
.doctor-stat-grid .stat-card span { font-size:10px; }
.doctor-analytics-card,.doctor-upcoming-card { margin-bottom:20px; padding:24px; border-radius:19px; }
.doctor-section-heading { display:flex; justify-content:space-between; align-items:flex-start; gap:18px; }
.doctor-section-heading h2,.doctor-upcoming-card .card-header h2,.doctor-slot-form-card .card-header h2,.doctor-released-slots .card-header h2 { margin:7px 0 6px; font-size:20px; letter-spacing:-.5px; }
.doctor-section-heading p { margin:0; color:#6f91a2; font-size:11px; line-height:1.6; }
.doctor-year-select { display:flex; align-items:center; gap:8px; color:#6f91a2; font-size:11px; }
.doctor-year-select select,.doctor-slot-form select,.doctor-slot-form input { min-width:0; padding:10px 11px; border:1px solid rgba(89,148,173,.2); border-radius:9px; outline:none; color:#dff7fb; background:#071d2b; }
.doctor-year-select select:focus,.doctor-slot-form select:focus,.doctor-slot-form input:focus { border-color:#2de0d2; box-shadow:0 0 0 3px rgba(45,224,210,.08); }
.doctor-chart-legend { display:flex; flex-wrap:wrap; gap:16px; margin:22px 0 8px; color:#7393a3; font-size:10px; }
.doctor-chart-legend span { display:flex; align-items:center; gap:7px; }
.doctor-chart-legend i { width:8px; height:8px; display:inline-block; border-radius:3px; }
.legend-total { background:#2de0d2; }.legend-scheduled { background:#1689d5; }.legend-completed { background:#54d69b; }
.doctor-month-chart { display:grid; grid-template-columns:repeat(12,minmax(0,1fr)); gap:clamp(5px,1.3vw,17px); height:220px; padding-top:10px; border-bottom:1px solid rgba(89,148,173,.15); background:repeating-linear-gradient(to bottom,transparent 0,transparent 53px,rgba(89,148,173,.08) 54px,transparent 55px); }
.doctor-month-column { display:flex; flex-direction:column; min-width:0; align-items:center; justify-content:flex-end; }
.doctor-month-bar-area { display:flex; flex:1; width:100%; flex-direction:column; justify-content:flex-end; align-items:center; min-height:0; }
.doctor-month-value { min-height:16px; margin-bottom:4px; color:#b9d8e2; font-size:10px; font-weight:800; }
.doctor-month-bar-stack { display:flex; flex-direction:column; justify-content:flex-start; overflow:hidden; width:min(100%,30px); min-height:2px; border-radius:7px 7px 2px 2px; background:rgba(45,224,210,.07); box-shadow:0 0 20px rgba(45,224,210,.04); }
.doctor-month-bar-stack span { display:block; width:100%; min-height:0; }.bar-scheduled { background:linear-gradient(180deg,#21c9d3,#147fc5); }.bar-completed { background:#4ed6a0; }.bar-other { background:#e6ad5a; }
.doctor-month-label { margin:9px 0 10px; color:#7090a0; font-size:10px; }
.doctor-chart-footnote { margin-top:14px; color:#547586; font-size:10px; line-height:1.6; }
.doctor-availability-layout { display:grid; grid-template-columns:minmax(280px,.9fr) minmax(0,1.1fr); align-items:start; gap:18px; }
.doctor-slot-form-card,.doctor-released-slots { padding:23px; border-radius:19px; }
.availability-icon { display:grid; place-items:center; width:36px; height:36px; border-radius:11px; color:#2de0d2; background:rgba(45,224,210,.09); font-size:23px; }
.doctor-slot-form { display:flex; flex-direction:column; gap:15px; margin-top:20px; }
.doctor-slot-form label { display:flex; flex-direction:column; gap:7px; color:#92adba; font-size:11px; font-weight:700; }
.doctor-slot-form input,.doctor-slot-form select { width:100%; min-height:42px; color-scheme:dark; }
.doctor-slot-form-row { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
.doctor-slot-preview { display:flex; flex-direction:column; gap:7px; padding:14px; border:1px solid rgba(45,224,210,.13); border-radius:12px; background:rgba(45,224,210,.04); }
.doctor-slot-preview span { color:#2de0d2; font-size:9px; font-weight:900; letter-spacing:1px; }.doctor-slot-preview strong { color:#e2f5f9; font-size:12px; }.doctor-slot-preview small { color:#7193a2; font-size:10px; }
.doctor-slot-form .auth-submit { width:100%; margin-top:2px; }
.success-message { padding:11px 13px; border:1px solid rgba(68,216,158,.2); border-radius:9px; color:#67e0b0; background:rgba(68,216,158,.07); font-size:11px; }
.released-slot-list { display:flex; flex-direction:column; gap:9px; margin-top:16px; }
.released-slot-row { display:flex; align-items:center; gap:12px; padding:13px; border:1px solid rgba(89,148,173,.12); border-radius:12px; background:rgba(4,20,32,.6); }
.released-slot-date { display:flex; flex:1; min-width:0; flex-direction:column; gap:6px; }.released-slot-date strong { color:#d8eff5; font-size:11px; }.released-slot-date span { color:#7293a3; font-size:10px; }
.availability-status { padding:6px 8px; border-radius:99px; font-size:9px; font-weight:900; }.availability-status.active { color:#5be2b0; background:rgba(68,216,158,.08); }.availability-status.inactive { color:#ff9b9b; background:rgba(255,107,107,.08); }
.remove-slot-button { width:27px; height:27px; border-radius:8px; color:#ff9b9b; background:rgba(255,107,107,.08); cursor:pointer; font-size:18px; }
.doctor-api-note { margin:18px 0 0; color:#58798a; font-size:10px; line-height:1.6; }
.doctor-photo-avatar { overflow:hidden; padding:0; background:#092a3c; }
.doctor-photo-avatar { flex: 0 0 78px; width: 78px; height: 92px; border-radius: 16px; }
.doctor-photo-avatar img { object-position: center top; }
.doctor-photo-fallback { display:flex; align-items:center; justify-content:center; color:#2de0d2; font-weight:900; font-size:22px; }
.doctor-welcome-photo { overflow:hidden; padding:0; position:relative; }
.doctor-welcome-photo img { width:100%; height:100%; object-fit:cover; object-position:center top; border-radius:inherit; display:block; }
.doctor-welcome-photo i { position:absolute; right:0; bottom:0; }
.user-avatar-photo { padding:0; overflow:hidden; }
.user-avatar-photo img { width:100%; height:100%; display:block; object-fit:cover; object-position:center top; border-radius:inherit; }

.doctor-photo-avatar img { display:block; width:100%; height:100%; object-fit:cover; }
.doctor-photo-fallback { padding:0; color:#2de0d2; background:rgba(45,224,210,.08); }

@media (max-width: 1100px) {
  .hero-visual {
    opacity: 0.3;
    right: -100px;
  }

  .services-grid {
    grid-template-columns:
      repeat(2, minmax(0, 1fr));
  }

  .specialization-grid {
    grid-template-columns:
      repeat(2, minmax(0, 1fr));
  }

  .doctor-grid {
    grid-template-columns:
      repeat(2, minmax(0, 1fr));
  }

  .ai-chat-layout {
    grid-template-columns: 1fr;
  }

  .ai-sidebar {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 850px) {
  .public-nav {
    display: none;
  }

  .hero-section {
    padding:
      70px 6%;
  }

  .hero-visual {
    display: none;
  }

  .auth-container {
    grid-template-columns: 1fr;
    max-width: 600px;
  }

  .auth-intro {
    text-align: center;
  }

  .auth-feature-list {
    align-items: center;
  }

  .dashboard-shell {
    grid-template-columns: 1fr;
  }

  .dashboard-sidebar {
    border-right: 0;
    border-bottom:
      1px solid
      rgba(89, 148, 173, 0.1);

    padding: 12px;
  }

  .sidebar-welcome,
  .sidebar-ai-card {
    display: none;
  }

  .dashboard-nav {
    flex-direction: row;
    overflow-x: auto;
  }

  .dashboard-nav-button {
    min-width: max-content;
  }

  .dashboard-main {
    padding: 20px;
  }

  .mini-services-grid {
    grid-template-columns:
      repeat(2, 1fr);
  }
}

@media (max-width: 650px) {
  .public-navbar {
    padding: 0 15px;
  }

  .nav-login-button {
    display: none;
  }

  .hero-content h1 {
    font-size: 45px;
    letter-spacing: -2px;
  }

  .hero-buttons {
    flex-direction: column;
  }

  .hero-primary,
  .hero-secondary {
    justify-content: center;
  }

  .hero-trust {
    gap: 15px;
    flex-wrap: wrap;
  }

  .public-section {
    padding:
      65px 20px;
  }

  .section-heading h2 {
    font-size: 29px;
  }

  .services-grid,
  .specialization-grid,
  .doctor-grid {
    grid-template-columns: 1fr;
  }

  .public-cta {
    margin:
      20px 15px
      50px;

    padding: 30px 20px;

    flex-direction: column;
    align-items: flex-start;
  }

  .public-cta h2 {
    font-size: 29px;
  }

  .public-footer {
    padding:
      25px 20px;

    flex-direction: column;
    align-items: flex-start;
    gap: 15px;
  }

  .auth-topbar {
    padding:
      0 15px;
  }

  .auth-container {
    margin:
      35px auto;

    padding:
      0 15px;
  }

  .auth-intro h1 {
    font-size: 42px;
  }

  .auth-card {
    padding: 22px;
  }

  .form-two-columns {
    grid-template-columns: 1fr;
  }

  .dashboard-topbar {
    padding: 0 10px;
  }

  .dashboard-user .online-status,
  .user-info {
    display: none;
  }

  .dashboard-main,
  .doctor-dashboard-shell {
    padding: 15px;
  }

  .dashboard-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .dashboard-heading h1 {
    font-size: 27px;
  }

  .overview-stat-grid {
    grid-template-columns: 1fr;
  }

  .overview-grid {
    grid-template-columns: 1fr;
  }

  .mini-services-grid {
    grid-template-columns: 1fr;
  }

  .dashboard-doctor-grid {
    grid-template-columns: 1fr;
  }

  .ai-sidebar {
    display: none;
  }

  .chat-messages {
    min-height: 420px;
    padding: 12px;
  }

  .chat-slot-grid {
    grid-template-columns: 1fr;
  }

  .chat-booking-options {
    width: calc(100% - 31px);
  }

  .booking-confirm-panel {
    flex-direction: column;
    align-items: stretch;
  }

  .booking-confirm-actions {
    width: 100%;
  }

  .booking-confirm-actions button {
    flex: 1;
  }

  .chat-quick-actions {
    overflow-x: auto;
  }

  .chat-quick-actions button {
    white-space: nowrap;
  }

  .appointment-row {
    grid-template-columns: 1fr;
    gap: 8px;
  }

  .doctor-table {
    min-width: 800px;
  }
}

/* =========================================================
   SMARTCARE AI CHAT REDESIGN
   Scrollable conversation + anchored composer + robot avatar
   ========================================================= */
.careflow-chat-layout {
  align-items: stretch;
  min-width: 0;
}

.careflow-chat-layout .chat-card {
  display: flex;
  flex-direction: column;
  min-width: 0;
  height: clamp(560px, calc(100vh - 245px), 820px);
  max-height: calc(100vh - 190px);
  overflow: hidden;
  border: 1px solid rgba(45, 224, 210, 0.14);
  border-radius: 20px;
  background:
    radial-gradient(ellipse at 12% 0%, rgba(17, 117, 139, 0.11), transparent 38%),
    linear-gradient(160deg, #061824 0%, #04111c 65%, #051522 100%);
  box-shadow: 0 22px 65px rgba(0, 0, 0, 0.18);
}

.careflow-chat-layout .chat-header {
  flex: 0 0 auto;
  height: 76px;
  padding: 0 22px;
  gap: 13px;
  background: rgba(3, 17, 28, 0.76);
  border-bottom: 1px solid rgba(112, 180, 201, 0.11);
}

.careflow-chat-layout .chat-header-text strong {
  color: #f1fbff;
  font-size: 14px;
  letter-spacing: -0.01em;
}

.careflow-chat-layout .chat-header-text span {
  color: #7295a8;
  font-size: 11px;
}

.robot-avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  background: linear-gradient(145deg, #2de0d2, #1398e8) !important;
  color: #042033 !important;
  box-shadow: 0 7px 20px rgba(22, 194, 208, 0.18);
  overflow: hidden;
}

.careflow-chat-layout .ai-icon.robot-avatar {
  width: 43px;
  height: 43px;
  border-radius: 14px;
  font-size: 23px;
}

.robot-avatar span {
  line-height: 1;
  filter: drop-shadow(0 1px 1px rgba(0, 0, 0, 0.16));
}

.careflow-chat-layout .chat-messages {
  flex: 1 1 auto;
  min-height: 0;
  height: auto;
  overflow-y: auto;
  overscroll-behavior: contain;
  scroll-behavior: smooth;
  padding: 24px clamp(14px, 3vw, 32px);
  gap: 18px;
  background-image: radial-gradient(rgba(91, 155, 176, 0.08) 0.7px, transparent 0.7px);
  background-size: 19px 19px;
  scrollbar-width: thin;
  scrollbar-color: rgba(45, 224, 210, 0.3) transparent;
}

.careflow-chat-layout .chat-messages::-webkit-scrollbar { width: 7px; }
.careflow-chat-layout .chat-messages::-webkit-scrollbar-thumb {
  background: rgba(45, 224, 210, 0.28);
  border-radius: 20px;
}

.careflow-chat-layout .chat-message {
  max-width: 100%;
  animation: careflow-message-in 220ms ease-out both;
}

.careflow-chat-layout .chat-message-ai { align-self: flex-start; }
.careflow-chat-layout .chat-message-user { align-self: flex-end; }

.careflow-chat-layout .message-bubble {
  gap: 10px;
  max-width: min(780px, 88%);
}

.careflow-chat-layout .message-ai-icon.robot-avatar {
  width: 34px;
  height: 34px;
  min-width: 34px;
  border-radius: 11px;
  font-size: 18px;
  margin-top: 2px;
}

.careflow-chat-layout .message-content {
  padding: 15px 17px;
  border: 1px solid rgba(100, 166, 190, 0.13);
  border-radius: 5px 17px 17px 17px;
  background: rgba(12, 33, 48, 0.93);
  color: #c6dce8;
  font-size: 13px;
  line-height: 1.75;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.careflow-chat-layout .chat-message-user .message-bubble {
  justify-content: flex-end;
}

.careflow-chat-layout .chat-message-user .message-content {
  border-color: rgba(45, 224, 210, 0.18);
  border-radius: 17px 5px 17px 17px;
  background: linear-gradient(135deg, rgba(12, 115, 137, 0.42), rgba(11, 72, 103, 0.55));
  color: #edffff;
}

.careflow-chat-layout .chat-quick-actions {
  flex: 0 0 auto;
  display: flex;
  flex-wrap: wrap;
  gap: 9px;
  padding: 13px 20px 11px;
  border-top: 1px solid rgba(112, 180, 201, 0.09);
  background: rgba(3, 17, 28, 0.96);
}

.careflow-chat-layout .chat-quick-actions button {
  padding: 10px 13px;
  border: 1px solid rgba(107, 169, 191, 0.13);
  border-radius: 10px;
  background: #0a2030;
  color: #8bb6c9;
  font-size: 11px;
  transition: border-color 160ms ease, color 160ms ease, transform 160ms ease;
}

.careflow-chat-layout .chat-quick-actions button:hover {
  color: #40eee0;
  border-color: rgba(45, 224, 210, 0.35);
  transform: translateY(-1px);
}

.careflow-chat-layout .chat-input-area {
  flex: 0 0 auto;
  align-items: center;
  gap: 11px;
  padding: 0 20px 12px;
  border-top: 0;
  background: rgba(3, 17, 28, 0.96);
}

.careflow-chat-layout .chat-input-area input {
  min-height: 52px;
  padding: 15px 17px;
  border-color: rgba(107, 169, 191, 0.17);
  border-radius: 13px;
  background: #04131f;
  color: #e8fbff;
  font-size: 13px;
}

.careflow-chat-layout .chat-input-area input::placeholder { color: #55788b; }
.careflow-chat-layout .chat-input-area input:focus {
  border-color: rgba(45, 224, 210, 0.62);
  box-shadow: 0 0 0 3px rgba(45, 224, 210, 0.07);
}

.careflow-chat-layout .chat-send-button {
  width: 52px;
  min-width: 52px;
  height: 52px;
  border-radius: 13px;
  color: #03131e;
  background: linear-gradient(135deg, #2de0d2, #159edb);
  box-shadow: 0 7px 20px rgba(21, 158, 219, 0.16);
}

.careflow-chat-layout .chat-send-button:disabled { opacity: 0.45; cursor: not-allowed; }

.careflow-chat-layout .chat-disclaimer {
  flex: 0 0 auto;
  padding: 0 20px 15px;
  background: rgba(3, 17, 28, 0.96);
  color: #547486;
  font-size: 10px;
}

.careflow-chat-layout .typing-indicator { padding: 13px 16px; }
.careflow-chat-layout .chat-scroll-anchor { width: 1px; height: 1px; flex: 0 0 1px; }

@keyframes careflow-message-in {
  from { opacity: 0; transform: translateY(7px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (max-width: 900px) {
  .careflow-chat-layout .chat-card {
    height: calc(100dvh - 250px);
    min-height: 500px;
    max-height: none;
  }
  .careflow-chat-layout .chat-messages { padding: 17px 13px; }
  .careflow-chat-layout .chat-quick-actions { flex-wrap: nowrap; overflow-x: auto; padding: 11px 13px; }
  .careflow-chat-layout .chat-quick-actions button { white-space: nowrap; }
  .careflow-chat-layout .chat-input-area { padding: 0 13px 10px; }
  .careflow-chat-layout .chat-disclaimer { padding: 0 13px 12px; }
  .careflow-chat-layout .message-bubble { max-width: 96%; }
}

@media (max-width: 1000px) {
  .doctor-stat-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }
  .doctor-availability-layout { grid-template-columns:1fr; }
  .doctor-welcome-panel { flex-wrap:wrap; }
}
@media (max-width: 650px) {
  .doctor-dashboard-shell { padding:18px 12px 30px; }
  .doctor-welcome-panel { padding:22px 18px; gap:16px; }
  .doctor-welcome-avatar { flex-basis:66px; width:66px; height:66px; border-radius:20px; font-size:20px; }
  .doctor-refresh { margin-left:auto; }
  .doctor-dashboard-tabs { width:100%; overflow-x:auto; }
  .doctor-dashboard-tabs button { padding:10px 12px; font-size:10px; }
  .doctor-analytics-card,.doctor-upcoming-card,.doctor-slot-form-card,.doctor-released-slots { padding:17px 13px; }
  .doctor-section-heading { flex-direction:column; }
  .doctor-month-chart { gap:3px; height:175px; }
  .doctor-month-label { font-size:8px; }
  .doctor-month-value { font-size:8px; }
  .doctor-chart-legend { gap:9px; font-size:9px; }
  .released-slot-row { gap:7px; padding:10px 8px; }
  .availability-status { font-size:8px; }
}

@media (prefers-reduced-motion: reduce) {
  .careflow-chat-layout .chat-message { animation: none; }
  .careflow-chat-layout .chat-messages { scroll-behavior: auto; }
}

/* Keep the chat on one viewport: only the conversation pane scrolls. */
.careflow-chat-layout {
  align-items: stretch;
  min-height: 0;
}
.careflow-chat-layout .chat-card {
  height: min(740px, calc(100dvh - 150px));
  min-height: 420px;
  max-height: calc(100dvh - 150px);
}
.careflow-chat-layout .chat-messages {
  min-height: 0;
  flex: 1 1 0;
  overscroll-behavior-y: contain;
  scroll-padding-bottom: 18px;
}
.careflow-chat-layout .chat-booking-options {
  margin-top: 8px;
}
.careflow-chat-layout .chat-slot-grid {
  gap: 8px;
}
.careflow-chat-layout .chat-slot-card {
  padding: 11px;
}
.careflow-chat-layout .message-content {
  line-height: 1.55;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}
.careflow-chat-layout .chat-disclaimer {
  line-height: 1.4;
}
@media (max-height: 800px) {
  .careflow-chat-layout .chat-card {
    height: calc(100dvh - 130px);
    max-height: calc(100dvh - 130px);
    min-height: 390px;
  }
  .careflow-chat-layout .chat-header { height: 68px; }
  .careflow-chat-layout .chat-messages { padding-top: 14px; padding-bottom: 14px; gap: 12px; }
  .careflow-chat-layout .chat-quick-actions { padding-top: 8px; padding-bottom: 8px; }
  .careflow-chat-layout .chat-disclaimer { padding-bottom: 9px; }
}
@media (max-width: 900px) {
  .careflow-chat-layout .chat-card {
    height: calc(100dvh - 190px);
    min-height: 390px;
    max-height: none;
  }
}

/* =========================================================
   SMARTCARE VISUAL POLISH — GLOBAL + AI CHAT EXPERIENCE
   CSS-only enhancement: preserves existing app logic and APIs.
   ========================================================= */
:root {
  --cf-aqua: #2de0d2;
  --cf-blue: #159edb;
  --cf-line: rgba(105, 183, 207, .16);
  --cf-panel: rgba(7, 27, 42, .88);
  --cf-muted: #82a8bb;
}

body {
  background:
    radial-gradient(ellipse at 12% 0%, rgba(20, 137, 162, .10), transparent 36%),
    radial-gradient(ellipse at 90% 22%, rgba(25, 110, 204, .09), transparent 32%),
    #04111d;
  background-attachment: fixed;
}

button, a, input, textarea, select {
  -webkit-tap-highlight-color: transparent;
}

button {
  transition: transform .18s ease, box-shadow .22s ease, border-color .2s ease,
    background-color .2s ease, color .2s ease, filter .2s ease;
}

button:not(:disabled):active { transform: translateY(1px) scale(.99); }
button:focus-visible, a:focus-visible, input:focus-visible, textarea:focus-visible, select:focus-visible {
  outline: 2px solid rgba(45, 224, 210, .8);
  outline-offset: 3px;
}

/* Gentle entrance for page sections, cards, and panels. */
.dashboard-main > *, .dashboard-heading, .doctor-welcome-panel,
.patient-overview-grid, .dashboard-stat-grid, .dashboard-card,
.auth-card, .hero-content, .hero-visual, .services-grid, .doctor-grid {
  animation: cf-rise-in .48s cubic-bezier(.2,.7,.2,1) both;
}

.dashboard-main > *:nth-child(2), .services-grid > *:nth-child(2),
.doctor-grid > *:nth-child(2) { animation-delay: 45ms; }
.dashboard-main > *:nth-child(3), .services-grid > *:nth-child(3),
.doctor-grid > *:nth-child(3) { animation-delay: 85ms; }
.dashboard-main > *:nth-child(4), .services-grid > *:nth-child(4),
.doctor-grid > *:nth-child(4) { animation-delay: 125ms; }

@keyframes cf-rise-in {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.dashboard-topbar, .public-navbar {
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  background-color: rgba(3, 16, 27, .88);
}

.dashboard-sidebar {
  background: linear-gradient(180deg, rgba(4, 19, 31, .98), rgba(4, 17, 29, .92));
  border-right-color: rgba(95, 171, 197, .13);
}

.dashboard-nav-button {
  position: relative;
  overflow: hidden;
  border-radius: 12px;
  transition: background .2s ease, transform .2s ease, color .2s ease;
}
.dashboard-nav-button::after {
  content: "";
  position: absolute;
  inset: 0 auto 0 0;
  width: 2px;
  background: var(--cf-aqua);
  transform: scaleY(0);
  transition: transform .2s ease;
}
.dashboard-nav-button:hover { transform: translateX(3px); background: rgba(45,224,210,.07); }
.dashboard-nav-button.active::after { transform: scaleY(1); }

.dashboard-card, .stat-card, .service-card, .doctor-card, .appointment-row,
.ai-sidebar-card, .chat-card, .doctor-analytics-card, .doctor-upcoming-card,
.doctor-slot-form-card, .doctor-released-slots {
  border-color: var(--cf-line);
  box-shadow: 0 12px 34px rgba(0, 0, 0, .10);
  transition: transform .22s ease, border-color .22s ease, box-shadow .22s ease;
}

.stat-card:hover, .service-card:hover, .doctor-card:hover,
.appointment-row:hover, .ai-sidebar-card:hover {
  transform: translateY(-3px);
  border-color: rgba(45, 224, 210, .28);
  box-shadow: 0 16px 36px rgba(0, 0, 0, .2), 0 0 0 1px rgba(45,224,210,.035);
}

.brand-mark, .user-avatar, .table-avatar, .service-icon, .ai-icon {
  box-shadow: 0 7px 24px rgba(21, 158, 219, .17);
}

.auth-card, .hero-visual, .dashboard-card, .stat-card, .service-card, .doctor-card {
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

/* Make headings clearer without changing layout or copy. */
.dashboard-heading h1, .doctor-welcome-copy h1, .hero-content h1 {
  letter-spacing: -.045em;
}
.dashboard-heading p, .doctor-welcome-copy p { line-height: 1.7; }

/* ---------------- Chatbot: immersive assistant workspace ---------------- */
.careflow-chat-layout {
  grid-template-columns: minmax(0, 1fr) 245px;
  gap: 18px;
}

.careflow-chat-layout .chat-card {
  position: relative;
  border: 1px solid rgba(69, 212, 215, .2);
  border-radius: 22px;
  background:
    radial-gradient(ellipse at 50% -10%, rgba(24, 135, 157, .13), transparent 50%),
    linear-gradient(155deg, rgba(7, 28, 43, .98), rgba(3, 15, 26, .98));
  box-shadow: 0 24px 70px rgba(0,0,0,.22), 0 0 0 1px rgba(45,224,210,.025),
    inset 0 1px 0 rgba(255,255,255,.025);
}

.careflow-chat-layout .chat-header {
  position: relative;
  min-height: 82px;
  background: linear-gradient(100deg, rgba(8, 35, 51, .97), rgba(4, 20, 33, .97));
}
.careflow-chat-layout .chat-header::after {
  content: "AI ASSISTANT";
  margin-left: auto;
  padding: 7px 10px;
  border: 1px solid rgba(45,224,210,.17);
  border-radius: 999px;
  color: #55e9df;
  background: rgba(45,224,210,.055);
  font-size: 9px;
  font-weight: 800;
  letter-spacing: .11em;
}
.careflow-chat-layout .online-dot {
  width: 8px;
  height: 8px;
  margin-left: 0;
  border-radius: 50%;
  background: #38e7b2;
  box-shadow: 0 0 0 4px rgba(56,231,178,.08), 0 0 16px rgba(56,231,178,.45);
  animation: cf-online-pulse 2.4s ease-in-out infinite;
}
@keyframes cf-online-pulse {
  0%, 100% { box-shadow: 0 0 0 3px rgba(56,231,178,.07), 0 0 10px rgba(56,231,178,.25); }
  50% { box-shadow: 0 0 0 6px rgba(56,231,178,.035), 0 0 18px rgba(56,231,178,.5); }
}

.careflow-chat-layout .ai-icon.robot-avatar {
  border: 1px solid rgba(255,255,255,.23);
  background: linear-gradient(145deg, #4bf4df 0%, #25b9df 52%, #2187ee 100%) !important;
  box-shadow: 0 8px 24px rgba(25, 186, 214, .25), inset 0 1px 0 rgba(255,255,255,.35);
}

.careflow-chat-layout .chat-messages {
  background-image: radial-gradient(rgba(95, 177, 199, .075) .75px, transparent .75px),
    linear-gradient(180deg, rgba(4,17,29,.08), rgba(4,17,29,.26));
  background-size: 22px 22px, auto;
  padding: 27px clamp(16px, 3.2vw, 36px);
  gap: 20px;
}
.careflow-chat-layout .chat-message-ai .message-content {
  position: relative;
  border: 1px solid rgba(110, 175, 199, .16);
  border-radius: 5px 18px 18px 18px;
  background: linear-gradient(145deg, rgba(13, 39, 56, .97), rgba(8, 28, 43, .97));
  box-shadow: 0 7px 22px rgba(0,0,0,.10), inset 0 1px 0 rgba(255,255,255,.02);
  color: #d3e6ee;
}
.careflow-chat-layout .chat-message-user .message-content {
  border: 1px solid rgba(45,224,210,.32);
  background: linear-gradient(135deg, rgba(9, 126, 142, .48), rgba(13, 73, 112, .65));
  box-shadow: 0 8px 24px rgba(4, 105, 126, .12), inset 0 1px 0 rgba(255,255,255,.05);
}
.careflow-chat-layout .chat-message-user .message-bubble { max-width: min(740px, 84%); }
.careflow-chat-layout .message-content { font-size: 13px; line-height: 1.8; }
.careflow-chat-layout .message-ai-icon.robot-avatar {
  border: 1px solid rgba(255,255,255,.2);
  box-shadow: 0 5px 15px rgba(21,158,219,.16);
}

/* Booking options feel like selectable appointment cards. */
.careflow-chat-layout .chat-booking-options {
  border: 1px solid rgba(45,224,210,.2);
  border-radius: 17px;
  background: linear-gradient(145deg, rgba(7,31,46,.96), rgba(5,22,35,.97));
  box-shadow: 0 14px 32px rgba(0,0,0,.14);
}
.careflow-chat-layout .chat-booking-title > div > span {
  color: #4be5dc;
  letter-spacing: .15em;
}
.careflow-chat-layout .chat-slot-grid {
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 11px;
}
.careflow-chat-layout .chat-slot-card {
  position: relative;
  border: 1px solid rgba(107,169,191,.16);
  border-radius: 14px;
  background: linear-gradient(145deg, rgba(10,35,51,.96), rgba(5,24,38,.98));
  box-shadow: 0 7px 18px rgba(0,0,0,.09);
  transition: transform .2s ease, border-color .2s ease, box-shadow .2s ease;
}
.careflow-chat-layout .chat-slot-card:hover {
  transform: translateY(-3px);
  border-color: rgba(45,224,210,.55);
  box-shadow: 0 12px 26px rgba(0,0,0,.18), 0 0 0 1px rgba(45,224,210,.05);
}
.careflow-chat-layout .chat-slot-card.chat-slot-selected {
  border-color: rgba(45,224,210,.8);
  box-shadow: 0 0 0 2px rgba(45,224,210,.11), 0 12px 28px rgba(0,0,0,.15);
}
.careflow-chat-layout .chat-slot-date { color: #c9e4ee; }
.careflow-chat-layout .chat-slot-time { color: #4ce9de; font-weight: 800; }

.careflow-chat-layout .chat-quick-actions {
  padding: 15px 20px 12px;
  gap: 9px;
  background: linear-gradient(180deg, rgba(4,20,32,.96), rgba(3,16,27,.99));
}
.careflow-chat-layout .chat-quick-actions button {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  border: 1px solid rgba(104,178,202,.2);
  border-radius: 999px;
  padding: 10px 15px;
  background: rgba(11,38,54,.86);
  color: #a7d1df;
  font-weight: 700;
}
.careflow-chat-layout .chat-quick-actions button:hover {
  background: rgba(45,224,210,.1);
  border-color: rgba(45,224,210,.48);
  color: #5cf2e6;
  box-shadow: 0 5px 18px rgba(45,224,210,.07);
  transform: translateY(-2px);
}
.careflow-chat-layout .chat-input-area {
  gap: 12px;
  padding: 2px 20px 14px;
  background: rgba(3,16,27,.99);
}
.careflow-chat-layout .chat-input-area input {
  border: 1px solid rgba(107,169,191,.2);
  border-radius: 15px;
  background: linear-gradient(145deg, #061b2a, #04131f);
  box-shadow: inset 0 1px 3px rgba(0,0,0,.15);
  transition: border-color .2s ease, box-shadow .2s ease, background .2s ease;
}
.careflow-chat-layout .chat-input-area input:focus {
  border-color: rgba(45,224,210,.72);
  background: #061a29;
  box-shadow: 0 0 0 4px rgba(45,224,210,.08), 0 0 25px rgba(45,224,210,.045);
}
.careflow-chat-layout .chat-send-button {
  position: relative;
  overflow: hidden;
  border-radius: 15px;
  background: linear-gradient(135deg, #4bf0dc, #20b9e7 62%, #2588ed);
  box-shadow: 0 8px 22px rgba(21,158,219,.23), inset 0 1px 0 rgba(255,255,255,.35);
  transition: transform .2s ease, box-shadow .2s ease, filter .2s ease;
}
.careflow-chat-layout .chat-send-button:not(:disabled):hover {
  transform: translateY(-2px);
  filter: saturate(1.12) brightness(1.06);
  box-shadow: 0 12px 27px rgba(21,158,219,.3), 0 0 0 4px rgba(45,224,210,.06);
}
.careflow-chat-layout .chat-disclaimer {
  border-top: 1px solid rgba(107,169,191,.08);
  color: #7192a3;
  padding-top: 10px;
}
.careflow-chat-layout .typing-indicator {
  border: 1px solid rgba(100,166,190,.14);
  border-radius: 5px 16px 16px 16px;
  background: rgba(12,33,48,.92);
}

/* Sidebar cards alongside the chatbot get a clearer visual hierarchy. */
.ai-sidebar-card {
  border-radius: 18px;
  background: linear-gradient(155deg, rgba(8,31,47,.96), rgba(4,19,31,.98));
}
.ai-sidebar-header { border-bottom-color: rgba(105,183,207,.12); }
.ai-sidebar-card:hover { border-color: rgba(45,224,210,.25); }

/* Respect accessibility preferences and keep motion subtle. */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: .01ms !important;
    animation-iteration-count: 1 !important;
    scroll-behavior: auto !important;
    transition-duration: .01ms !important;
  }
}

@media (max-width: 900px) {
  .careflow-chat-layout { grid-template-columns: minmax(0, 1fr); }
  .careflow-chat-layout .chat-header::after { display: none; }
  .careflow-chat-layout .chat-slot-grid { grid-template-columns: minmax(0, 1fr); }
}
@media (max-width: 600px) {
  .careflow-chat-layout .chat-header { padding: 0 14px; min-height: 70px; }
  .careflow-chat-layout .chat-header-text strong { font-size: 12px; }
  .careflow-chat-layout .chat-header-text span { font-size: 10px; }
  .careflow-chat-layout .chat-message-user .message-bubble,
  .careflow-chat-layout .message-bubble { max-width: 100%; }
  .careflow-chat-layout .chat-quick-actions { gap: 7px; }
  .careflow-chat-layout .chat-quick-actions button { padding: 9px 12px; }
}



/* =========================================================
   PATIENT REGISTRATION - COMPACT BLOOD GROUP SELECT
   ========================================================= */

/* Keep this field compact and override the stacked auth-form label styles. */
.auth-form .blood-group-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  padding: 10px 12px;
  border: 1px solid rgba(91, 219, 226, 0.20);
  border-radius: 12px;
  background: linear-gradient(145deg, rgba(11, 39, 54, 0.72), rgba(5, 23, 36, 0.82));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.035);
}

.auth-form .blood-group-field .blood-group-label {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: flex-start;
  gap: 9px;
  width: 100%;
  margin: 0;
  text-align: left;
  color: #d9edf5;
  font-size: 12px;
  font-weight: 750;
  line-height: 1.3;
}

.blood-group-label-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 30px;
  width: 30px;
  height: 30px;
  border-radius: 9px;
  color: #38e1d2;
  background: rgba(39, 220, 208, 0.12);
  border: 1px solid rgba(39, 220, 208, 0.2);
  font-size: 15px;
}

.blood-group-label small {
  display: block;
  margin-top: 2px;
  color: #7899aa;
  font-size: 10px;
  font-weight: 500;
}

.blood-group-field .field-optional {
  margin-left: auto;
  padding: 4px 6px;
  border-radius: 6px;
  color: #61dcd4;
  background: rgba(39, 220, 208, 0.08);
  font-size: 7px;
  font-weight: 800;
  letter-spacing: 0.06em;
  white-space: nowrap;
}

.blood-group-select-wrap {
  position: relative;
  display: flex;
  align-items: center;
  width: 100%;
}

.blood-group-select-icon {
  position: absolute;
  left: 12px;
  z-index: 1;
  pointer-events: none;
  font-size: 15px;
}

.auth-form .blood-group-field .blood-group-select {
  display: block;
  width: 100%;
  min-height: 42px;
  box-sizing: border-box;
  appearance: none;
  -webkit-appearance: none;
  padding: 0 38px 0 39px;
  border: 1px solid rgba(111, 157, 179, 0.28);
  border-radius: 9px;
  outline: none;
  color: #edfaff;
  background: rgba(2, 17, 29, 0.88);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: border-color 160ms ease, box-shadow 160ms ease, background 160ms ease;
}

.blood-group-select:invalid { color: #91aab8; }
.blood-group-select option { color: #edfaff; background: #071b2a; }
.blood-group-select:hover { border-color: rgba(47, 220, 211, 0.55); }
.blood-group-select:focus {
  border-color: #2bd9cf;
  box-shadow: 0 0 0 3px rgba(43, 217, 207, 0.12);
}

.blood-group-chevron {
  position: absolute;
  right: 13px;
  top: 50%;
  transform: translateY(-58%);
  color: #65dcd6;
  font-size: 21px;
  line-height: 1;
  pointer-events: none;
}

.auth-form .blood-group-field .blood-group-help {
  margin: 0;
  color: #7f9cab;
  font-size: 10px;
  line-height: 1.35;
}

@media (max-width: 520px) {
  .auth-form .blood-group-field { padding: 9px 10px; }
  .blood-group-field .field-optional { font-size: 6px; letter-spacing: 0.03em; }
}

/* Patient blood group badges: dashboard profile and chatbot header. */
.user-info .patient-blood-group-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  width: fit-content;
  max-width: 170px;
  margin-top: 3px;
  padding: 4px 7px;
  border: 1px solid rgba(45, 224, 210, .20);
  border-radius: 999px;
  color: #9cece5;
  background: rgba(45, 224, 210, .07);
  font-size: 8px;
  font-weight: 700;
  white-space: nowrap;
}
.user-info .patient-blood-group-chip span { color: #ff7795; font-size: 10px; }
.chat-patient-blood-group {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
  padding: 7px 10px;
  border: 1px solid rgba(45, 224, 210, .18);
  border-radius: 999px;
  color: #8eb5c5;
  background: rgba(45, 224, 210, .055);
  font-size: 10px;
  white-space: nowrap;
}
.chat-patient-blood-group > span:first-child { color: #ff7795; font-size: 12px; }
.chat-patient-blood-group strong { color: #55e9df; font-size: 10px; }
.careflow-chat-layout .online-dot { margin-left: 2px; flex: 0 0 8px; }
@media (max-width: 700px) {
  .chat-patient-blood-group { gap: 4px; padding: 6px 7px; font-size: 8px; }
  .chat-patient-blood-group > span:nth-child(2) { display: none; }
  .chat-patient-blood-group strong { font-size: 9px; }
}



/* FINAL VISUAL FIXES: patient chart contrast, card spacing, and stacked profile controls */
.patient-health-analytics,
.patient-chart-panel,
.doctor-analytics-card,
.doctor-status-card,
.doctor-upcoming-card {
  color: #eaf7ff !important;
  box-sizing: border-box;
}
.patient-health-analytics { overflow:hidden; }
.patient-health-analytics .card-header { display:flex!important; align-items:flex-start!important; justify-content:space-between!important; gap:18px!important; }
.patient-health-analytics .analytics-period { flex:0 0 auto; font-size:10px!important; line-height:1.2!important; padding:9px 13px!important; margin:2px 0 0 auto; border-radius:999px!important; color:#6ce9df!important; background:rgba(45,224,210,.08)!important; }
.patient-analytics-grid { align-items:stretch!important; gap:18px!important; }
.patient-chart-panel,.doctor-status-card { padding:22px!important; border-radius:18px!important; background:linear-gradient(145deg,#0b2537 0%,#071a29 75%,#0b2031 100%)!important; border:1px solid rgba(93,176,204,.24)!important; box-shadow:0 12px 30px rgba(0,0,0,.16),inset 0 1px 0 rgba(255,255,255,.035)!important; }
.analytics-panel-heading { margin-bottom:18px!important; }
.analytics-panel-heading h3,.doctor-status-card h3 { color:#f0f9ff!important; font-size:17px!important; letter-spacing:-.025em!important; }
.analytics-panel-heading>span,.doctor-status-card p { color:#87aabd!important; line-height:1.5!important; }
.patient-line-chart { width:100%!important; height:auto!important; min-height:230px!important; overflow:visible!important; }
.patient-line-chart .chart-grid-line { stroke:rgba(127,174,198,.18)!important; stroke-width:1.2!important; }
.patient-line-chart .chart-line { fill:none!important; stroke-width:4!important; stroke-linecap:round!important; stroke-linejoin:round!important; }
.patient-line-chart .chart-line-total { stroke:#35e2d1!important; filter:drop-shadow(0 0 5px rgba(53,226,209,.3))!important; }
.patient-line-chart .chart-line-scheduled { stroke:#529cff!important; }
.patient-line-chart .chart-line-completed { stroke:#c084fc!important; }
.patient-line-chart .chart-point-total { fill:#35e2d1!important; stroke:#071a29!important; stroke-width:2.5!important; }
.patient-line-chart .chart-month-label { fill:#a2c3d2!important; font-size:13px!important; font-weight:650!important; }
.patient-line-chart polygon { fill:url(#patientAreaFill)!important; opacity:1!important; }
.patient-line-chart text { fill:#a2c3d2!important; }
.patient-line-legend { display:flex!important; align-items:center!important; flex-wrap:wrap!important; gap:12px 18px!important; margin-top:8px!important; color:#9ab9c8!important; font-size:12px!important; }
.patient-line-legend span { display:inline-flex!important; align-items:center!important; gap:8px!important; white-space:nowrap; }
.patient-line-legend i { flex:0 0 10px; width:10px!important; height:10px!important; border-radius:50%!important; }
.patient-mix-panel { display:flex!important; flex-direction:column!important; }
.patient-donut { flex:0 0 auto; width:172px!important; height:172px!important; margin:20px auto!important; border:0!important; }
.patient-donut:after { inset:16px!important; background:#081c2b!important; border:1px solid rgba(127,174,198,.2)!important; }
.patient-donut-center { z-index:2!important; gap:3px!important; }
.patient-donut-center strong { color:#f4fbff!important; font-size:30px!important; }
.patient-donut-center span { color:#9ab9c8!important; font-size:12px!important; }
.patient-mix-legend { gap:12px!important; margin-top:auto!important; }
.patient-mix-legend>div { display:grid!important; grid-template-columns:11px minmax(0,1fr) auto!important; gap:10px!important; align-items:center!important; padding:10px 11px!important; border:1px solid rgba(104,164,191,.12)!important; border-radius:10px!important; background:rgba(5,19,31,.45)!important; color:#a7c1ce!important; }
.patient-mix-legend strong { color:#f1fbff!important; font-weight:850!important; }
.patient-chart-note { color:#86a7b8!important; font-size:11px!important; line-height:1.5!important; }

/* Header order: AI status, patient name/profile and blood group, then logout. */
.dashboard-user { gap:12px!important; align-items:center!important; }
.dashboard-user .online-status { order:0!important; }
.dashboard-user .user-avatar,.dashboard-user .avatar,.dashboard-user .profile-avatar { order:1!important; flex:0 0 auto!important; }
.dashboard-user .user-info { order:2!important; display:flex!important; flex-direction:column!important; align-items:flex-start!important; justify-content:center!important; gap:5px!important; min-width:150px!important; max-width:230px!important; }
.dashboard-user .user-info>strong { display:block!important; max-width:230px!important; color:#f1f8ff!important; font-size:13px!important; line-height:1.2!important; white-space:nowrap!important; overflow:hidden!important; text-overflow:ellipsis!important; }
.dashboard-user .user-info>span:not(.patient-blood-group-chip) { color:#7798a9!important; font-size:9px!important; font-weight:800!important; line-height:1.1!important; letter-spacing:.08em!important; }
.dashboard-user .user-info .patient-blood-group-chip { display:inline-flex!important; align-self:flex-start!important; width:max-content!important; max-width:230px!important; min-height:27px!important; margin:0!important; padding:6px 10px!important; gap:6px!important; border-radius:9px!important; font-size:10px!important; line-height:1.2!important; white-space:nowrap!important; }
.dashboard-user .logout-button { order:3!important; flex:0 0 auto!important; margin-left:4px!important; min-height:38px!important; padding:0 16px!important; border-radius:11px!important; white-space:nowrap!important; }

/* Doctor bar chart and status pie chart as separate, readable dashboard cards. */
.doctor-analytics-card { padding:24px!important; border:1px solid rgba(83,164,194,.22)!important; border-radius:22px!important; background:linear-gradient(145deg,#071b2a,#061522 72%,#091e2d)!important; box-shadow:0 18px 42px rgba(0,0,0,.15)!important; }
.doctor-section-heading { display:flex!important; align-items:flex-start!important; justify-content:space-between!important; gap:20px!important; }
.doctor-section-heading h2 { margin:8px 0!important; color:#f1f9ff!important; font-size:25px!important; font-weight:850!important; letter-spacing:-.035em!important; }
.doctor-section-heading p { color:#86aabd!important; line-height:1.6!important; }
.doctor-chart-legend { display:flex!important; flex-wrap:wrap!important; align-items:center!important; gap:12px 18px!important; margin:20px 0 14px!important; color:#9ab9c8!important; font-size:12px!important; }
.doctor-chart-legend>span { display:inline-flex!important; align-items:center!important; gap:8px!important; }
.doctor-month-chart { display:grid!important; grid-template-columns:repeat(12,minmax(0,1fr))!important; gap:8px!important; align-items:stretch!important; min-height:255px!important; padding:18px 12px 0!important; border:1px solid rgba(94,159,186,.13)!important; border-radius:16px!important; background:repeating-linear-gradient(to bottom,rgba(7,27,42,.12) 0,rgba(7,27,42,.12) 49px,rgba(123,176,198,.1) 50px,rgba(7,27,42,.12) 51px)!important; }
.doctor-month-column { display:flex!important; flex-direction:column!important; justify-content:flex-end!important; align-items:stretch!important; min-width:0!important; padding:6px 3px 12px!important; border:0!important; border-radius:8px!important; background:transparent!important; }
.doctor-month-bar-area { position:relative!important; display:flex!important; flex:1 1 auto!important; min-height:190px!important; align-items:flex-end!important; justify-content:center!important; }
.doctor-month-bar-stack { display:flex!important; flex-direction:column!important; justify-content:flex-end!important; width:min(68%,34px)!important; min-height:0!important; overflow:hidden!important; border-radius:7px 7px 3px 3px!important; background:linear-gradient(180deg,#35e2d1,#229acb)!important; box-shadow:0 5px 16px rgba(53,226,209,.13)!important; }
.doctor-month-bar-stack .bar-scheduled { display:block!important; background:#529cff!important; }
.doctor-month-bar-stack .bar-completed { display:block!important; background:#c084fc!important; }
.doctor-month-bar-stack .bar-other { display:block!important; background:#ff8d78!important; }
.doctor-month-value { position:absolute!important; top:0!important; color:#d8f4ff!important; font-size:10px!important; font-weight:800!important; }
.doctor-month-label { display:block!important; padding-top:10px!important; text-align:center!important; color:#91b4c5!important; font-size:10px!important; font-weight:700!important; }
.doctor-analytics-lower-grid { display:grid!important; grid-template-columns:minmax(0,1fr) minmax(250px,.85fr)!important; gap:18px!important; margin-top:20px!important; }
.doctor-status-card { min-width:0!important; padding:22px!important; }
.doctor-pie-layout { display:grid!important; grid-template-columns:160px minmax(0,1fr)!important; align-items:center!important; gap:22px!important; }
.doctor-pie-chart { width:154px!important; height:154px!important; margin:14px auto!important; border-radius:50%!important; box-shadow:0 0 32px rgba(76,156,255,.1)!important; }
.doctor-pie-chart:before { inset:17px!important; background:#081b2a!important; border:1px solid rgba(127,174,198,.18)!important; }
.doctor-pie-chart>div { position:relative!important; z-index:2!important; gap:3px!important; }
.doctor-pie-chart strong { color:#f3fbff!important; font-size:27px!important; font-weight:900!important; }
.doctor-pie-chart span { color:#91b4c5!important; font-size:11px!important; }
.doctor-pie-legend { display:grid!important; gap:10px!important; }
.doctor-pie-legend>div { display:grid!important; grid-template-columns:10px minmax(0,1fr) auto!important; align-items:center!important; gap:9px!important; padding:10px 11px!important; border:1px solid rgba(104,164,191,.12)!important; border-radius:10px!important; background:rgba(5,19,31,.45)!important; color:#a5c1ce!important; font-size:12px!important; }
.doctor-pie-legend strong { color:#f4fbff!important; font-variant-numeric:tabular-nums!important; }
.doctor-insight-tile { display:flex!important; gap:13px!important; align-items:center!important; margin-top:12px!important; padding:14px!important; border:1px solid rgba(105,167,193,.15)!important; border-radius:13px!important; background:linear-gradient(110deg,rgba(12,39,56,.85),rgba(5,23,36,.85))!important; }
.doctor-insight-tile>div { display:flex!important; flex-direction:column!important; gap:4px!important; }
.doctor-insight-tile strong { color:#f2fbff!important; font-size:22px!important; line-height:1!important; }
.doctor-insight-tile span:last-child { color:#8aabba!important; font-size:11px!important; }
.doctor-chart-footnote { color:#7f9faf!important; font-size:11px!important; line-height:1.5!important; padding-top:12px!important; }
@media(max-width:900px) { .doctor-analytics-lower-grid,.patient-analytics-grid { grid-template-columns:1fr!important; } .patient-mix-panel { display:grid!important; grid-template-columns:minmax(0,1fr) minmax(150px,.8fr)!important; align-items:center!important; } .patient-mix-panel .analytics-panel-heading { grid-column:1/-1; } .patient-donut { grid-column:1; grid-row:2; } .patient-mix-legend { grid-column:2; grid-row:2; } }
@media(max-width:650px) { .dashboard-topbar { height:auto!important; min-height:0!important; padding:12px!important; } .dashboard-user { display:flex!important; flex-wrap:wrap!important; justify-content:flex-end!important; gap:8px!important; max-width:100%!important; } .dashboard-user .online-status { flex-basis:100%; text-align:right!important; } .dashboard-user .user-info { min-width:0!important; max-width:calc(100vw - 145px)!important; } .dashboard-user .user-info .patient-blood-group-chip { max-width:100%!important; white-space:normal!important; } .dashboard-user .logout-button { padding:0 11px!important; } .doctor-month-chart { gap:2px!important; padding-inline:5px!important; min-height:210px!important; } .doctor-month-bar-area { min-height:155px!important; } .doctor-month-label { font-size:8px!important; } .doctor-analytics-card { padding:14px!important; } .doctor-section-heading h2 { font-size:20px!important; } .doctor-pie-layout { grid-template-columns:1fr!important; justify-items:center!important; } .doctor-pie-legend { width:100%!important; } .patient-mix-panel { display:flex!important; } }


/* Final dashboard fixes: patient identity order and visible status analytics. */
.dashboard-user-patient { display:flex!important; align-items:center!important; gap:14px!important; }
.dashboard-user-patient .online-status { order:0!important; }
.dashboard-user-patient .user-avatar { order:1!important; }
.dashboard-user-patient .user-info { order:2!important; display:flex!important; flex-direction:column!important; align-items:flex-start!important; gap:5px!important; min-width:145px!important; }
.dashboard-user-patient .user-info>strong { order:0!important; }
.dashboard-user-patient .user-info>span:not(.patient-blood-group-chip) { display:none!important; order:1!important; }
.dashboard-user-patient .user-info .patient-blood-group-chip { order:2!important; margin-top:2px!important; }
.dashboard-user-patient .logout-button { order:3!important; margin-left:4px!important; white-space:nowrap!important; }
.doctor-pie-chart { overflow:hidden!important; background-color:#1a3445!important; }
.doctor-pie-chart:before { pointer-events:none!important; }
.doctor-pie-chart>div { position:relative!important; }
.doctor-pie-legend>div>span:first-child { width:10px!important; height:10px!important; border-radius:3px!important; display:block!important; }
.doctor-month-bar-stack .bar-rescheduled { display:block!important; background:#b784ff!important; }
.insight-icon.purple { color:#c7a0ff!important; background:rgba(183,132,255,.13)!important; }
.legend-cancelled { background:#ff8d78!important; }.legend-rescheduled { background:#b784ff!important; }
@media(max-width:760px) { .dashboard-user-patient { width:auto!important; flex-wrap:wrap!important; } .dashboard-user-patient .online-status { flex-basis:auto!important; text-align:left!important; } .dashboard-user-patient .user-info { display:flex!important; max-width:calc(100vw - 210px)!important; min-width:0!important; } .dashboard-user-patient .logout-button { order:3!important; } }
@media(max-width:520px) { .dashboard-user-patient .user-info .patient-blood-group-chip { white-space:normal!important; } .doctor-month-chart { grid-template-columns:repeat(6,minmax(0,1fr))!important; } }


/* PATIENT-ONLY dashboard polish; doctor dashboard styling is intentionally untouched. */
.patient-analytics-redesign {
  position: relative;
  padding: 26px !important;
  border-radius: 24px !important;
  border: 1px solid rgba(80, 190, 214, .20) !important;
  background:
    radial-gradient(circle at 10% 0%, rgba(40, 205, 211, .075), transparent 34%),
    linear-gradient(145deg, #071a29 0%, #081f30 58%, #071725 100%) !important;
  box-shadow: 0 18px 48px rgba(0, 0, 0, .18), inset 0 1px 0 rgba(255,255,255,.035) !important;
}
.patient-analytics-redesign .patient-analytics-header { align-items: center !important; margin-bottom: 24px !important; }
.patient-analytics-redesign .card-header h2 { font-size: clamp(21px, 2vw, 27px) !important; letter-spacing: -.04em !important; margin: 8px 0 !important; }
.patient-analytics-redesign .card-description { margin-top: 7px !important; color: #89aabb !important; font-size: 13px !important; }
.patient-analytics-redesign .analytics-period { display: inline-flex !important; align-items: center !important; gap: 8px !important; white-space: nowrap !important; border: 1px solid rgba(45,224,210,.2) !important; }
.analytics-live-dot { width: 7px; height: 7px; display: inline-block; border-radius: 50%; background: #3ee2c7; box-shadow: 0 0 12px rgba(62,226,199,.7); }
.patient-analytics-grid-new { display: grid !important; grid-template-columns: minmax(0, 1.35fr) minmax(300px, .85fr) !important; gap: 20px !important; }
.patient-analytics-grid-new .patient-chart-panel { min-width: 0 !important; padding: 24px !important; border-radius: 20px !important; background: linear-gradient(155deg, rgba(13,39,57,.98), rgba(7,25,39,.98)) !important; border: 1px solid rgba(103,177,203,.17) !important; box-shadow: 0 12px 30px rgba(0,0,0,.12), inset 0 1px 0 rgba(255,255,255,.035) !important; }
.patient-analytics-grid-new .analytics-panel-heading { display: flex !important; justify-content: space-between !important; align-items: center !important; gap: 12px !important; margin-bottom: 25px !important; }
.patient-analytics-grid-new .analytics-panel-heading > div { display: flex; align-items: center; gap: 10px; }
.patient-analytics-grid-new .analytics-panel-heading h3 { margin: 0 !important; color: #f2f9ff !important; font-size: 17px !important; font-weight: 800 !important; letter-spacing: -.025em !important; }
.patient-analytics-grid-new .analytics-panel-heading > span { color: #7295a9 !important; font-size: 11px !important; white-space: nowrap; }
.analytics-icon-bubble { display: inline-grid; place-items: center; width: 34px; height: 34px; border-radius: 11px; color: #42e3d2; background: rgba(53,226,209,.10); border: 1px solid rgba(53,226,209,.13); font-size: 19px; }
.analytics-icon-bubble.purple { color: #c29aff; background: rgba(183,132,255,.12); border-color: rgba(183,132,255,.18); }
.patient-bar-chart { display: grid; grid-template-columns: 24px minmax(0,1fr); gap: 10px; height: 248px; padding-top: 5px; }
.patient-bar-y-labels { display: flex; flex-direction: column; justify-content: space-between; padding: 0 0 31px; color: #65889c; font-size: 10px; text-align: right; }
.patient-bar-plot { position: relative; min-width: 0; height: 100%; }
.patient-bar-gridline { position: absolute; left: 0; right: 0; height: 1px; border-top: 1px dashed rgba(132,177,198,.16); pointer-events: none; }
.patient-bar-columns { position: absolute; inset: 0; display: grid; grid-template-columns: repeat(6,minmax(0,1fr)); gap: clamp(7px, 1.8vw, 18px); }
.patient-bar-column { position: relative; display: flex; flex-direction: column; align-items: center; min-width: 0; }
.patient-bar-tooltip { z-index: 1; position: absolute; transform: translateY(-5px); color: #dff8ff; font-size: 10px; font-weight: 800; }
.patient-bar-track { position: absolute; top: 4px; bottom: 31px; width: min(100%, 34px); display: flex; align-items: flex-end; justify-content: center; }
.patient-stacked-bar { display: flex; flex-direction: column; justify-content: flex-end; width: 100%; min-height: 5px; overflow: hidden; border-radius: 9px 9px 4px 4px; background: #173448; box-shadow: 0 5px 18px rgba(0,0,0,.18); transition: height .35s ease, filter .2s ease; }
.patient-bar-column:hover .patient-stacked-bar { filter: brightness(1.2); }
.bar-segment { display: block; min-height: 0; width: 100%; }
.bar-segment.completed { background: linear-gradient(180deg,#52edbf,#23b98b); }
.bar-segment.scheduled { background: linear-gradient(180deg,#6bb4ff,#387fe8); }
.bar-segment.rescheduled { background: linear-gradient(180deg,#d0a7ff,#9661ec); }
.bar-segment.cancelled { background: linear-gradient(180deg,#ffa096,#f16d7e); }
.bar-segment.other { background: #f6c76b; }
.patient-empty-bar { height: 3px; width: 100%; border-radius: 99px; background: #234255; }
.patient-bar-month { position: absolute; bottom: 0; left: 0; right: 0; color: #8eafc0; text-align: center; font-size: 11px; font-weight: 700; }
.patient-legend-new { display: flex !important; flex-wrap: wrap !important; gap: 11px 15px !important; margin-top: 19px !important; }
.patient-legend-new span { display: inline-flex !important; align-items: center !important; gap: 7px !important; color: #9ab7c7 !important; font-size: 11px !important; }
.patient-legend-new i { width: 8px !important; height: 8px !important; display: inline-block !important; border-radius: 3px !important; }
.patient-donut-wrap { display: flex; justify-content: center; padding: 2px 0 18px; }
.patient-donut-new { width: 174px !important; height: 174px !important; margin: 0 auto !important; border-radius: 50% !important; position: relative; filter: drop-shadow(0 12px 24px rgba(0,0,0,.2)); }
.patient-donut-new::after { content: ""; position: absolute; inset: 13px !important; border-radius: 50%; background: linear-gradient(145deg,#0b2537,#071a29) !important; border: 1px solid rgba(128,186,208,.13) !important; }
.patient-donut-new .patient-donut-center { position: absolute; inset: 0; display: flex !important; flex-direction: column !important; align-items: center !important; justify-content: center !important; gap: 4px !important; z-index: 2; }
.patient-donut-new .patient-donut-center strong { color: #f4fbff !important; font-size: 31px !important; line-height: 1.1 !important; letter-spacing: -.05em; }
.patient-donut-new .patient-donut-center span { color: #87aabd !important; font-size: 11px !important; }
.patient-mix-legend-new { display: grid !important; gap: 8px !important; margin-top: 0 !important; }
.patient-mix-legend-new > div { display: grid !important; grid-template-columns: 9px minmax(0,1fr) auto auto !important; align-items: center !important; gap: 9px !important; padding: 11px 12px !important; border: 1px solid rgba(104,164,191,.12) !important; border-radius: 12px !important; background: rgba(3,16,28,.44) !important; }
.patient-mix-legend-new .mix-dot { width: 8px !important; height: 8px !important; border-radius: 3px !important; }
.patient-mix-legend-new > div > span:nth-child(2) { color: #a9c3d0 !important; font-size: 12px !important; }
.patient-mix-legend-new strong { color: #f3faff !important; font-size: 13px !important; }
.patient-mix-legend-new small { min-width: 35px; text-align: right; color: #6f94a9; font-size: 10px; font-weight: 750; }
.patient-analytics-redesign .patient-chart-note { display: flex !important; align-items: center !important; gap: 8px !important; margin-top: 18px !important; color: #7194a8 !important; font-size: 11px !important; }
.patient-analytics-redesign .patient-chart-note > span { display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: #35e2d1; }
.dashboard-user-patient { gap: 16px !important; }
.dashboard-user-patient .user-info { min-width: 135px !important; }
.dashboard-user-patient .user-info > strong { font-size: 14px !important; font-weight: 850 !important; letter-spacing: -.02em !important; }
.dashboard-user-patient .user-info .patient-blood-group-chip { max-width: none !important; padding: 8px 12px !important; margin-top: 3px !important; gap: 7px !important; border-radius: 12px !important; color: #c4f7f2 !important; background: linear-gradient(135deg,rgba(45,224,210,.12),rgba(30,131,197,.10)) !important; border-color: rgba(58,218,215,.25) !important; font-size: 10px !important; box-shadow: inset 0 1px 0 rgba(255,255,255,.035); }
.dashboard-user-patient .user-info .patient-blood-group-chip > span { color: #ff819d !important; font-size: 12px !important; }
.dashboard-user-patient .logout-button { padding: 12px 19px !important; border: 1px solid rgba(126,176,198,.13) !important; border-radius: 13px !important; color: #d9eaf4 !important; background: linear-gradient(145deg,#102b3c,#0a1d2b) !important; font-weight: 800 !important; transition: transform .2s ease, border-color .2s ease, background .2s ease; }
.dashboard-user-patient .logout-button:hover { transform: translateY(-1px); border-color: rgba(55,226,209,.35) !important; background: linear-gradient(145deg,#12394a,#0a2535) !important; }
.patient-table-blood-group { display: inline-flex !important; align-items: center; gap: 4px; margin-top: 5px; padding: 4px 7px; border: 1px solid rgba(45,224,210,.15); border-radius: 7px; color: #8edbd5 !important; background: rgba(45,224,210,.06); font-size: 10px !important; line-height: 1.35; white-space: nowrap; }
.patient-table-blood-group > span { color: #ff819d; }
@media (max-width: 900px) {
  .patient-analytics-grid-new { grid-template-columns: minmax(0,1fr) !important; }
  .patient-mix-panel-new { display: grid; grid-template-columns: minmax(0,1fr) minmax(0,1fr); column-gap: 18px; align-items: center; }
  .patient-mix-panel-new .analytics-panel-heading { grid-column: 1 / -1; }
  .patient-mix-panel-new .patient-donut-wrap { padding-bottom: 0; }
}
@media (max-width: 650px) {
  .patient-analytics-redesign { padding: 16px !important; }
  .patient-analytics-grid-new .patient-chart-panel { padding: 16px !important; }
  .patient-analytics-redesign .card-header { flex-wrap: wrap !important; }
  .patient-mix-panel-new { display: block; }
  .dashboard-user-patient { gap: 9px !important; }
  .dashboard-user-patient .user-info { min-width: 0 !important; max-width: 150px !important; }
  .dashboard-user-patient .user-info .patient-blood-group-chip { white-space: normal !important; padding: 6px 8px !important; }
}

/* FINAL PATIENT HEADER FIX — keep profile vertically aligned and unclipped */
.dashboard-topbar {
  height: auto !important;
  min-height: 88px !important;
  align-items: center !important;
  overflow: visible !important;
}
.dashboard-topbar .dashboard-user-patient {
  display: flex !important;
  flex-direction: row !important;
  flex-wrap: nowrap !important;
  align-items: center !important;
  justify-content: flex-end !important;
  gap: 12px !important;
  min-width: 0 !important;
  height: auto !important;
  overflow: visible !important;
  padding: 8px 0 !important;
}
.dashboard-topbar .dashboard-user-patient > .online-status {
  order: 0 !important;
  flex: 0 0 auto !important;
  align-self: center !important;
  white-space: nowrap !important;
  margin: 0 4px 0 0 !important;
}
.dashboard-topbar .dashboard-user-patient > .patient-avatar {
  order: 1 !important;
  position: static !important;
  flex: 0 0 42px !important;
  width: 42px !important;
  height: 42px !important;
  margin: 0 !important;
  align-self: center !important;
}
.dashboard-topbar .dashboard-user-patient > .patient-profile-stack {
  order: 2 !important;
  position: static !important;
  display: flex !important;
  flex: 0 1 170px !important;
  flex-direction: column !important;
  align-items: flex-start !important;
  justify-content: center !important;
  gap: 4px !important;
  width: auto !important;
  min-width: 130px !important;
  max-width: 190px !important;
  height: auto !important;
  min-height: 0 !important;
  margin: 0 !important;
  padding: 0 !important;
  overflow: visible !important;
  transform: none !important;
  line-height: normal !important;
}
.dashboard-topbar .dashboard-user-patient .patient-profile-name {
  display: block !important;
  position: static !important;
  width: 100% !important;
  max-width: 100% !important;
  margin: 0 !important;
  padding: 0 !important;
  color: #f2f8ff !important;
  font-size: 15px !important;
  font-weight: 800 !important;
  line-height: 1.25 !important;
  white-space: nowrap !important;
  overflow: hidden !important;
  text-overflow: ellipsis !important;
}
.dashboard-topbar .dashboard-user-patient .patient-profile-role {
  display: block !important;
  position: static !important;
  margin: 0 !important;
  padding: 0 !important;
  color: #7899ad !important;
  font-size: 10px !important;
  font-weight: 800 !important;
  letter-spacing: 1px !important;
  line-height: 1.25 !important;
}
.dashboard-topbar .dashboard-user-patient .patient-blood-group-chip {
  display: inline-flex !important;
  position: static !important;
  align-items: center !important;
  justify-content: flex-start !important;
  flex-wrap: nowrap !important;
  gap: 6px !important;
  width: max-content !important;
  max-width: 100% !important;
  min-height: 34px !important;
  margin: 3px 0 0 !important;
  padding: 7px 10px !important;
  border: 1px solid rgba(57, 228, 208, .25) !important;
  border-radius: 11px !important;
  background: linear-gradient(135deg, rgba(23,179,174,.14), rgba(18,115,157,.12)) !important;
  color: #a9d8df !important;
  font-size: 11px !important;
  font-weight: 650 !important;
  line-height: 1.2 !important;
  white-space: nowrap !important;
  overflow: hidden !important;
  text-overflow: ellipsis !important;
}
.dashboard-topbar .dashboard-user-patient .patient-blood-group-chip > span:first-child {
  flex: 0 0 auto !important;
  color: #ff7d9e !important;
}
.dashboard-topbar .dashboard-user-patient .patient-blood-group-chip strong {
  color: #63eadb !important;
  font-weight: 850 !important;
}
.dashboard-topbar .dashboard-user-patient > .patient-logout {
  order: 3 !important;
  position: static !important;
  display: inline-flex !important;
  flex: 0 0 auto !important;
  align-items: center !important;
  justify-content: center !important;
  gap: 7px !important;
  min-width: 88px !important;
  min-height: 42px !important;
  margin: 0 0 0 2px !important;
  padding: 0 14px !important;
  border-radius: 13px !important;
  white-space: nowrap !important;
  line-height: 1 !important;
}
@media (max-width: 760px) {
  .dashboard-topbar {
    min-height: 90px !important;
    padding-top: 10px !important;
    padding-bottom: 10px !important;
  }
  .dashboard-topbar .dashboard-user-patient {
    width: auto !important;
    max-width: 100% !important;
    flex-wrap: nowrap !important;
    gap: 9px !important;
  }
  .dashboard-topbar .dashboard-user-patient > .patient-profile-stack {
    flex: 0 1 150px !important;
    min-width: 112px !important;
    max-width: 165px !important;
  }
  .dashboard-topbar .dashboard-user-patient > .patient-avatar {
    flex-basis: 38px !important;
    width: 38px !important;
    height: 38px !important;
  }
  .dashboard-topbar .dashboard-user-patient > .patient-logout {
    min-width: 78px !important;
    min-height: 40px !important;
    padding: 0 10px !important;
  }
}
@media (max-width: 520px) {
  .dashboard-topbar .dashboard-user-patient {
    gap: 7px !important;
  }
  .dashboard-topbar .dashboard-user-patient > .online-status {
    font-size: 10px !important;
    gap: 5px !important;
  }
  .dashboard-topbar .dashboard-user-patient > .patient-profile-stack {
    flex-basis: 125px !important;
    min-width: 100px !important;
    max-width: 135px !important;
  }
  .dashboard-topbar .dashboard-user-patient .patient-blood-group-chip {
    gap: 4px !important;
    padding: 6px 7px !important;
    font-size: 10px !important;
  }
  .dashboard-topbar .dashboard-user-patient > .patient-logout {
    min-width: 68px !important;
    padding: 0 8px !important;
    font-size: 11px !important;
  }
}



/* =========================================================
   MOBILE + TABLET RESPONSIVE PATCH
   ========================================================= */
html { -webkit-text-size-adjust: 100%; text-size-adjust: 100%; }
body { overflow-x: clip; }
img, svg, video, canvas { max-width: 100%; }
button, a, input, select, textarea { touch-action: manipulation; -webkit-tap-highlight-color: transparent; }
[id] { scroll-margin-top: 84px; }

/* hamburger + in-menu doctor button: hidden on desktop */
.nav-menu-toggle { display: none; }
.nav-menu-doctor { display: none; }

/* ---------- tablets and phones ---------- */
@media (max-width: 850px) {
  .public-navbar { gap: 10px; }

  .nav-actions { margin-left: auto; align-items: center; }

  .nav-menu-toggle {
    display: inline-flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 4px;
    width: 42px;
    height: 42px;
    padding: 0;
    border-radius: 10px;
    cursor: pointer;
    background: rgba(30, 76, 102, 0.28);
  }
  .nav-menu-toggle span {
    display: block;
    width: 18px;
    height: 2px;
    border-radius: 2px;
    background: #a5c0cd;
    transition: transform .2s ease, opacity .2s ease;
  }
  .nav-menu-toggle.is-open span:nth-child(1) { transform: translateY(6px) rotate(45deg); }
  .nav-menu-toggle.is-open span:nth-child(2) { opacity: 0; }
  .nav-menu-toggle.is-open span:nth-child(3) { transform: translateY(-6px) rotate(-45deg); }

  .public-nav.is-open {
    display: flex;
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    flex-direction: column;
    gap: 0;
    margin: 0;
    padding: 6px 5% 14px;
    background: rgba(3, 15, 27, 0.98);
    border-bottom: 1px solid rgba(102, 173, 200, 0.18);
    box-shadow: 0 18px 40px rgba(0, 0, 0, 0.45);
  }
  .public-nav.is-open a,
  .public-nav.is-open .nav-menu-doctor {
    display: block;
    width: 100%;
    padding: 15px 4px;
    border-bottom: 1px solid rgba(102, 173, 200, 0.1);
    font-size: 15px;
    text-align: left;
    color: #a5c0cd;
    background: none;
    cursor: pointer;
  }
  .public-nav.is-open .nav-menu-doctor { border-bottom: 0; font-weight: 700; color: #32ded3; }

  /* inputs must be 16px or iPhones zoom the page on focus */
  input, textarea, select,
  .auth-form input,
  .chat-input-area input { font-size: 16px !important; }
}

/* ---------- phones ---------- */
@media (max-width: 650px) {
  /* Doctor Sign In moves into the menu (the navbar button is hidden) */
  .nav-menu-doctor { display: block; }
  .brand > div:last-child span { display: none; }
  .brand-mark { width: 36px; height: 36px; font-size: 22px; }
  .nav-login-button, .nav-primary-button { font-size: 12px; padding: 11px 13px; white-space: nowrap; }

  .hero-section { padding: 50px 20px 60px; min-height: 0; }
  .hero-content h1 { font-size: clamp(32px, 10vw, 45px); line-height: 1.05; letter-spacing: -1.2px; }
  .hero-buttons { width: 100%; }
  .hero-primary, .hero-secondary { width: 100%; }
  .hero-trust span { font-size: 11px; }
  .hero-trust strong { font-size: 18px; }

  .auth-intro h1 { font-size: clamp(30px, 9vw, 42px); }
  .auth-card { padding: 20px 16px; }

  .doctor-table-wrapper { -webkit-overflow-scrolling: touch; }

  .dashboard-nav-button, .doctor-dashboard-tabs button { font-size: 12px; }
}

/* ---------- small phones (360px and below) ---------- */
@media (max-width: 380px) {
  .public-section { padding: 50px 14px; }
  .dashboard-main, .doctor-dashboard-shell { padding: 12px 10px; }
  .nav-primary-button { padding: 10px 11px; font-size: 11px; }
}

/* ---------- touch devices: comfortable tap size ---------- */
@media (pointer: coarse) {
  .nav-login-button, .nav-primary-button, .dashboard-nav-button,
  .logout-button, .hero-primary, .hero-secondary,
  .chat-quick-actions button { min-height: 44px; }
}
/* ===== END MOBILE + TABLET PATCH ===== */

`;
