import { z } from "zod";

export const NoteRecordSchema = z.object({
  id: z.string().uuid(),
  agent_id: z.string(),
  type: z.string(),
  content: z.string(),
  priority: z.string(),
  created_at: z.string(),
  subsystem: z.string(),
  metadata: z.record(z.string(), z.any()).default({}),
});

export type NoteRecord = z.infer<typeof NoteRecordSchema>;
