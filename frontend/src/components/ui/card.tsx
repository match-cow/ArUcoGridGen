import type { HTMLAttributes } from "react";
import { cn } from "../../lib/utils";
export const Card = ({ className, ...props }: HTMLAttributes<HTMLDivElement>) => <div className={cn("card", className)} {...props} />;
export const CardContent = ({ className, ...props }: HTMLAttributes<HTMLDivElement>) => <div className={cn("card-content", className)} {...props} />;
