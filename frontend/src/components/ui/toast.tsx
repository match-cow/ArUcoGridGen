import * as ToastPrimitive from "@radix-ui/react-toast";
import type { ComponentProps } from "react";
export const ToastProvider = ToastPrimitive.Provider;
export function Toast(props: ComponentProps<typeof ToastPrimitive.Root>) { return <ToastPrimitive.Root className="toast" {...props} />; }
export const ToastTitle = ToastPrimitive.Title;
export const ToastDescription = ToastPrimitive.Description;
export function ToastAction(props: ComponentProps<typeof ToastPrimitive.Action>) { return <ToastPrimitive.Action className="toast-action" {...props} />; }
export function ToastViewport() { return <ToastPrimitive.Viewport className="toast-viewport" />; }
