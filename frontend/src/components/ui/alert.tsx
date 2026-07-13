import type { HTMLAttributes } from "react";
import { cn } from "../../lib/utils";
export const Alert = ({ className, ...props }: HTMLAttributes<HTMLDivElement>) => <div role="alert" className={cn("alert", className)} {...props} />;
