import * as React from "react"
import * as ProgressPrimitive from "@radix-ui/react-progress"

import { cn } from "@/lib/utils"

const Progress = React.forwardRef<
  React.ElementRef<typeof ProgressPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof ProgressPrimitive.Root>
>(({ className, value, ...props }, ref) => (
  <ProgressPrimitive.Root
    ref={ref}
    className={cn(
      "relative h-1.5 w-full overflow-hidden rounded-full",
      className
    )}
    style={{ background: 'rgba(255,255,255,0.1)' }}
    {...props}
  >
    <ProgressPrimitive.Indicator
      className="h-full flex-1 transition-all duration-500 rounded-full"
      style={{
        transform: `translateX(-${100 - (value || 0)}%)`,
        background: value && value >= 85
          ? 'linear-gradient(90deg, #22C55E, #16a34a)'
          : value && value >= 70
          ? 'linear-gradient(90deg, #F59E0B, #d97706)'
          : 'linear-gradient(90deg, #EF4444, #dc2626)',
      }}
    />
  </ProgressPrimitive.Root>
))
Progress.displayName = ProgressPrimitive.Root.displayName

export { Progress }
