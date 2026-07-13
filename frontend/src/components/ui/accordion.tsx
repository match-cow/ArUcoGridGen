import * as AccordionPrimitive from "@radix-ui/react-accordion";
import { ChevronDown } from "lucide-react";
import type { ComponentProps } from "react";
import { cn } from "../../lib/utils";
export const Accordion = AccordionPrimitive.Root;
export function AccordionItem({ className, ...props }: ComponentProps<typeof AccordionPrimitive.Item>) { return <AccordionPrimitive.Item className={cn("accordion-item", className)} {...props} />; }
export function AccordionTrigger({ children, className, ...props }: ComponentProps<typeof AccordionPrimitive.Trigger>) { return <AccordionPrimitive.Header><AccordionPrimitive.Trigger className={cn("accordion-trigger", className)} {...props}>{children}<ChevronDown aria-hidden size={16} /></AccordionPrimitive.Trigger></AccordionPrimitive.Header>; }
export function AccordionContent({ className, ...props }: ComponentProps<typeof AccordionPrimitive.Content>) { return <AccordionPrimitive.Content className={cn("accordion-content", className)} {...props}><div>{props.children}</div></AccordionPrimitive.Content>; }
