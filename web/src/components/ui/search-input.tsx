import * as React from "react"
import { Search, X } from "lucide-react"
import { cn } from "@/lib/utils"
import { Input } from "@/components/ui/input"
import { VoiceInputButton } from "@/components/voice/VoiceInputButton"
import { useVoiceInput } from "@/hooks/use-voice-input"
import { useVoiceSettings } from "@/hooks/use-settings"

export interface SearchInputProps extends React.ComponentProps<"input"> {
  onClear?: () => void
}

const SearchInput = React.forwardRef<HTMLInputElement, SearchInputProps>(
  ({ className, value, onChange, onClear, ...props }, ref) => {
    // Voice settings from backend
    const { data: voiceSettings } = useVoiceSettings()
    const lang = voiceSettings?.input_language?.value ?? "en-US"

    const voiceInput = useVoiceInput({
      lang,
      continuous: false,
      onResult: React.useCallback(
        (transcript: string) => {
          if (onChange) {
            // Synthesize onChange event with voice transcript
            const event = {
              target: { value: transcript },
              currentTarget: { value: transcript },
            } as React.ChangeEvent<HTMLInputElement>
            onChange(event)
          }
        },
        [onChange]
      ),
    })

    // Handle clear
    const handleClear = () => {
      if (onClear) {
        onClear()
      } else if (onChange) {
        // Synthesize an event if onClear isn't provided but onChange is
        const event = {
          target: { value: "" },
          currentTarget: { value: "" },
        } as React.ChangeEvent<HTMLInputElement>
        onChange(event)
      }
    }

    // Handle escape key
    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Escape" && value) {
        e.preventDefault()
        e.stopPropagation()
        handleClear()
      }
      props.onKeyDown?.(e)
    }

    return (
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground pointer-events-none" />
        <Input
          ref={ref}
          value={value}
          onChange={onChange}
          onKeyDown={handleKeyDown}
          className={cn("pl-9 pr-16", className)}
          {...props}
        />
        <div className="absolute right-1 top-1/2 -translate-y-1/2 flex items-center gap-0.5">
          {value && (
            <button
              type="button"
              onClick={handleClear}
              className="text-muted-foreground hover:text-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 rounded-sm p-0.5"
              aria-label="Clear search"
            >
              <X className="h-4 w-4" />
            </button>
          )}
          {voiceInput.isSupported && (
            <VoiceInputButton
              isListening={voiceInput.isListening}
              isSupported={voiceInput.isSupported}
              error={voiceInput.error}
              onToggle={voiceInput.toggleListening}
              className="h-7 w-7"
            />
          )}
        </div>
      </div>
    )
  }
)
SearchInput.displayName = "SearchInput"

export { SearchInput }
