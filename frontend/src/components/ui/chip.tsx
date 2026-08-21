import { Toggle as TogglePrimitive } from "@base-ui/react/toggle"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const chipVariants = cva(
  "inline-flex shrink-0 items-center justify-center gap-1.5 rounded-full border border-border bg-background px-3.5 py-1.5 text-sm font-medium whitespace-nowrap transition-colors outline-none select-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50 disabled:pointer-events-none disabled:opacity-50 data-[pressed]:border-brand-primary data-[pressed]:bg-brand-blush data-[pressed]:text-brand-primary data-[pressed]:hover:bg-brand-blush-strong"
)

function Chip({
  className,
  ...props
}: TogglePrimitive.Props & VariantProps<typeof chipVariants>) {
  return (
    <TogglePrimitive
      data-slot="chip"
      className={cn(chipVariants({ className }))}
      {...props}
    />
  )
}

export { Chip, chipVariants }
