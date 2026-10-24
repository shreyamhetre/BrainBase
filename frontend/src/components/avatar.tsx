import { initials } from "@/lib/format";

const SIZES = { sm: "h-8 w-8 text-[11px]", md: "h-9 w-9 text-xs", lg: "h-16 w-16 text-xl" };

// A circle with the person's initials. Admins get the brand orange; everyone else navy.
export function Avatar({ name, admin = false, size = "md" }: { name: string; admin?: boolean; size?: keyof typeof SIZES }) {
  return (
    <span aria-hidden="true"
      className={`inline-flex shrink-0 select-none items-center justify-center rounded-full font-semibold tracking-wide ${SIZES[size]} ${
        admin ? "bg-brand text-white" : "bg-navy/10 text-navy"}`}>
      {initials(name)}
    </span>
  );
}
