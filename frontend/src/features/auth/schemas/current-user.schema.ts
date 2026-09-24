import { z } from "zod";

export const currentUserSchema = z.object({
  id: z.number().int(),
  email: z.string().email(),
  name: z.string().min(1).max(128),
  is_admin: z.boolean(),
});

export type CurrentUser = z.infer<typeof currentUserSchema>;
