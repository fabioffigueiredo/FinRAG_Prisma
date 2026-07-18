"use client"

import * as React from "react"
import { Eye, EyeOff } from "lucide-react"

import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupInput } from "@/components/ui/input-group"

/** Campo de senha com botão de olho pra alternar entre texto oculto/visível
 * — nunca muda o `name`/autocomplete do campo, só o `type` em runtime. */
function PasswordInput({ className, ...props }: React.ComponentProps<"input">) {
  const [visivel, setVisivel] = React.useState(false)

  return (
    <InputGroup className={className}>
      <InputGroupInput type={visivel ? "text" : "password"} {...props} />
      <InputGroupAddon align="inline-end">
        <InputGroupButton
          type="button"
          aria-label={visivel ? "Ocultar senha" : "Mostrar senha"}
          onClick={() => setVisivel((v) => !v)}
        >
          {visivel ? <EyeOff /> : <Eye />}
        </InputGroupButton>
      </InputGroupAddon>
    </InputGroup>
  )
}

export { PasswordInput }
