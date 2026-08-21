import { Button as ButtonPrimitive } from "@base-ui/react/button"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const iconButtonVariants = cva(
  "group/icon-button inline-flex shrink-0 items-center justify-center rounded-full transition-all outline-none select-none focus-visible:ring-3 focus-visible:ring-ring/50 active:not-aria-[haspopup]:translate-y-px disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        filled: "bg-brand-primary text-white hover:bg-brand-primary/90",
        outline:
          "border-2 border-brand-primary bg-transparent text-brand-primary hover:bg-brand-blush",
      },
      size: {
        default: "size-[60px] [&_svg:not([class*='size-'])]:size-6",
        sm: "size-10 [&_svg:not([class*='size-'])]:size-4",
        lg: "size-16 [&_svg:not([class*='size-'])]:size-7",
      },
    },
    defaultVariants: {
      variant: "filled",
      size: "default",
    },
  }
)

function IconButton({
  className,
  variant = "filled",
  size = "default",
  ...props
}: ButtonPrimitive.Props & VariantProps<typeof iconButtonVariants>) {
  return (
    <ButtonPrimitive
      data-slot="icon-button"
      className={cn(iconButtonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { IconButton, iconButtonVariants }
