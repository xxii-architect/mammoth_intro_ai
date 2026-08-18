import { z } from "zod";

export const NoteRecordSchema = z.object({
  id: z.string().uuid(),
  title: z.string().default('Untitled'),
  body: z.string().default(''),
  content: z.string().default(''),
  created_at: z.string().default(''),
  updated_at: z.string().default(''),
  agent_id: z.string().default(''),
  source: z.enum(['personal', 'agent']).default('personal'),
  type: z.string().default('personal_note'),
  priority: z.string().default('normal'),
  subsystem: z.string().default('general'),
  metadata: z.record(z.string(), z.any()).default({}),
});

export type NoteRecord = z.infer<typeof NoteRecordSchema>;
