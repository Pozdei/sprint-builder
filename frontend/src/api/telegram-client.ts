// Telegram-дайджест: ручная отправка/тест по активному конфигу.

import { api } from "./client";

export interface TelegramSendResult {
  sent: boolean;
  count: number;
}

export async function sendTodayDigest(): Promise<TelegramSendResult> {
  const r = await api.post("/api/telegram/send-today", null);
  return r.data;
}

export async function sendTestMessage(): Promise<TelegramSendResult> {
  const r = await api.post("/api/telegram/test", null);
  return r.data;
}
