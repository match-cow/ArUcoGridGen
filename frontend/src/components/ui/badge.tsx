import type { HTMLAttributes } from "react";
import { cn } from "../../lib/utils";
export const Badge = ({ className, ...props }: HTMLAttributes<HTMLSpanElement>) => <span className={cn("badge", className)} {...props} />;
