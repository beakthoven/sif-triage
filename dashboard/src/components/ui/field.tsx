import * as React from "react"
import { CircleAlert } from "lucide-react"
import { cn } from "@/lib/utils"

type FieldProps = {
  label: React.ReactNode
  hint?: React.ReactNode
  error?: React.ReactNode
  required?: boolean
  children: React.ReactElement
  className?: string
}

/**
 * Wraps a single form control. The control receives `id`, `required` and
 * `aria-invalid` via cloning; hint/error are wired as `aria-describedby`.
 * Pass exactly one control (Input, Textarea, Select, or any element taking
 * these DOM props) as `children`.
 */
function Field({ label, hint, error, required = false, children, className }: FieldProps) {
  const hintId = React.useId()
  const errorId = React.useId()
  const controlId = React.useId()

  const describedBy = [hint != null ? hintId : null, error != null ? errorId : null]
    .filter(Boolean)
    .join(" ")

  const control = React.isValidElement(children)
    ? React.cloneElement(
        children as unknown as React.ReactElement<{
          id?: string
          required?: boolean
          "aria-invalid"?: boolean
          "aria-describedby"?: string
        }>,
        {
          id: controlId,
          required: required || undefined,
          "aria-invalid": (error != null) || undefined,
          "aria-describedby": describedBy || undefined,
        },
      )
    : children

  return (
    <div className={cn("flex w-full min-w-0 flex-col gap-2", className)}>
      <label htmlFor={controlId} className="text-sm font-medium text-content-primary">
        {label}
        {required && <span aria-hidden="true" className="ml-1 text-status-danger">*</span>}
      </label>
      {control}
      {hint != null && (
        <p id={hintId} className="text-sm text-content-secondary">
          {hint}
        </p>
      )}
      {error != null && (
        <p id={errorId} role="alert" className="flex items-start gap-1 text-sm text-status-danger">
          <CircleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          {error}
        </p>
      )}
    </div>
  )
}

export { Field }
