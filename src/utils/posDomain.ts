export interface ParsedNotification {
  amountCop: number;
  senderName: string;
  rawNotification: string;
}

const UNIDADES = [
  "",
  "un",
  "dos",
  "tres",
  "cuatro",
  "cinco",
  "seis",
  "siete",
  "ocho",
  "nueve",
];

const ESPECIALES: Record<number, string> = {
  10: "diez",
  11: "once",
  12: "doce",
  13: "trece",
  14: "catorce",
  15: "quince",
  16: "dieciséis",
  17: "diecisiete",
  18: "dieciocho",
  19: "diecinueve",
  20: "veinte",
  21: "veintiún",
  22: "veintidós",
  23: "veintitrés",
  24: "veinticuatro",
  25: "veinticinco",
  26: "veintiséis",
  27: "veintisiete",
  28: "veintiocho",
  29: "veintinueve",
};

const DECENAS = [
  "",
  "",
  "",
  "treinta",
  "cuarenta",
  "cincuenta",
  "sesenta",
  "setenta",
  "ochenta",
  "noventa",
];

const CENTENAS = [
  "",
  "ciento",
  "doscientos",
  "trescientos",
  "cuatrocientos",
  "quinientos",
  "seiscientos",
  "setecientos",
  "ochocientos",
  "novecientos",
];

function convertirMenorMil(n: number): string {
  if (n === 0) return "";
  if (n === 100) return "cien";
  const partes: string[] = [];
  const centenas = Math.floor(n / 100);
  const resto = n % 100;
  if (centenas > 0) partes.push(CENTENAS[centenas]);
  if (resto > 0) {
    if (ESPECIALES[resto]) {
      partes.push(ESPECIALES[resto]);
    } else if (resto < 10) {
      partes.push(UNIDADES[resto]);
    } else {
      const dec = Math.floor(resto / 10);
      const uni = resto % 10;
      partes.push(uni === 0 ? DECENAS[dec] : `${DECENAS[dec]} y ${UNIDADES[uni]}`);
    }
  }
  return partes.join(" ");
}

export function enteroALetras(numero: number): string {
  if (numero === 0) return "cero";
  const millones = Math.floor(numero / 1_000_000);
  const miles = Math.floor((numero % 1_000_000) / 1_000);
  const unidades = numero % 1_000;
  const partes: string[] = [];

  if (millones > 0) {
    partes.push(millones === 1 ? "un millón" : `${convertirMenorMil(millones)} millones`);
  }
  if (miles > 0) {
    partes.push(miles === 1 ? "mil" : `${convertirMenorMil(miles)} mil`);
  }
  if (unidades > 0) {
    partes.push(convertirMenorMil(unidades));
  }
  return partes.join(" ").trim();
}

export function montoALetras(monto: number): string {
  const entero = Math.floor(monto);
  const centavos = Math.round((monto - entero) * 100);
  let sufijo = entero === 1 ? "peso" : "pesos";
  if (entero >= 1_000_000 && entero % 1_000_000 === 0) {
    sufijo = "de pesos";
  }
  const textoEntero = enteroALetras(entero);
  if (centavos > 0) {
    const textoCent = enteroALetras(centavos);
    return `${textoEntero} ${sufijo} con ${textoCent} ${centavos === 1 ? "centavo" : "centavos"}`;
  }
  return `${textoEntero} ${sufijo}`;
}

export function buildTtsPhrase(monto: number): string {
  return `Pago por el valor de ${montoALetras(monto)}`;
}

export function formatCop(monto: number): string {
  return "$" + monto.toLocaleString("es-CO", { minimumFractionDigits: 0, maximumFractionDigits: 2 });
}

const INCOME_PATTERNS = [
  /(?:recibiste|te\s+enviaron|pago\s+recibido(?:\s+por)?|recibiste\s+un\s+env[ií]o(?:\s+de)?)\s*(?:por\s+)?\$?\s*([\d.,]+)\s+(?:de|por\s+parte\s+de)\s+([A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9\s.'-]+?)(?:\s+en\s+tu\s+nequi|[.!,\n]|$)/i,
  /(?:recibiste|te\s+enviaron|pago\s+recibido)\s*(?:por\s+)?\$?\s*([\d.,]+)/i,
];

const NEGATIVE_KEYWORDS = [
  "enviaste",
  "pagaste",
  "retiraste",
  "recargaste",
  "transferencia rechazada",
  "código de verificación",
  "clave dinámica",
];

function normalizeColombianAmount(raw: string): number | null {
  let cleaned = raw.trim().replace(/\s+/g, "");
  if (!cleaned) return null;

  if (cleaned.includes(".") && cleaned.includes(",")) {
    cleaned = cleaned.replace(/\./g, "").replace(",", ".");
  } else if (cleaned.includes(",")) {
    const parts = cleaned.split(",");
    cleaned = parts[parts.length - 1].length === 2 ? cleaned.replace(",", ".") : cleaned.replace(/,/g, "");
  } else if (cleaned.includes(".")) {
    const parts = cleaned.split(".");
    cleaned = parts[parts.length - 1].length === 3 ? cleaned.replace(/\./g, "") : cleaned;
  }

  const parsed = Number(cleaned);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

export function parseNequiNotification(rawText: string): ParsedNotification | null {
  const combined = rawText.trim().replace(/\s+/g, " ");
  if (!combined) return null;
  const lower = combined.toLowerCase();
  if (NEGATIVE_KEYWORDS.some((kw) => lower.includes(kw))) {
    return null;
  }

  for (let i = 0; i < INCOME_PATTERNS.length; i++) {
    const match = combined.match(INCOME_PATTERNS[i]);
    if (!match) continue;
    const amount = normalizeColombianAmount(match[1]);
    if (!amount) continue;
    const sender = i === 0 && match[2] ? match[2].trim() : "Cliente Nequi";
    return {
      amountCop: amount,
      senderName: sender || "Cliente Nequi",
      rawNotification: combined,
    };
  }
  return null;
}

export function speakSpanishPosPhrase(phrase: string): void {
  try {
    // 1. Timbre suave de caja POS con Web Audio API
    const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (AudioCtx) {
      const ctx = new AudioCtx();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(880, ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(1318.5, ctx.currentTime + 0.14);
      gain.gain.setValueAtTime(0.12, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.36);
    }
  } catch {
    // Ignorar si AudioContext no está disponible
  }

  // 2. Síntesis de voz en español
  if (typeof window !== "undefined" && "speechSynthesis" in window) {
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(phrase);
    const voices = window.speechSynthesis.getVoices();
    const esVoice =
      voices.find((v) => v.lang.toLowerCase().startsWith("es-co")) ||
      voices.find((v) => v.lang.toLowerCase().startsWith("es"));
    if (esVoice) {
      utterance.voice = esVoice;
    }
    utterance.lang = "es-CO";
    utterance.rate = 0.96;
    window.speechSynthesis.speak(utterance);
  }
}
