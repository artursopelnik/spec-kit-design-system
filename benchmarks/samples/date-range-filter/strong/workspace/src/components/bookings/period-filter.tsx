"use client";

import { useState } from "react";
import type { DateRange } from "react-day-picker";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { FormMessage } from "@/components/ui/form";

type Props = {
  value?: DateRange;
  onChange: (range?: DateRange) => void;
};

export function PeriodFilter({ value, onChange }: Props) {
  const [error, setError] = useState<string | null>(null);

  function onSelect(range?: DateRange) {
    if (range?.from && range.to && range.to < range.from) {
      setError("The end of the period falls before its start.");
      return;
    }
    setError(null);
    onChange(range);
  }

  return (
    <div className="flex flex-col gap-2">
      <Popover>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            size="default"
            aria-invalid={error ? true : undefined}
            className="min-h-11 w-72 justify-start text-left font-normal text-foreground"
          >
            {value?.from ? formatRange(value) : <span className="text-muted-foreground">Any period</span>}
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-auto bg-popover p-2" align="start">
          <Calendar
            mode="range"
            selected={value}
            onSelect={onSelect}
            numberOfMonths={1}
            className="sm:hidden"
          />
          <Calendar
            mode="range"
            selected={value}
            onSelect={onSelect}
            numberOfMonths={2}
            className="hidden sm:block"
          />
        </PopoverContent>
      </Popover>
      {error ? <FormMessage className="text-destructive">{error}</FormMessage> : null}
    </div>
  );
}

function formatRange(range: DateRange) {
  const format = new Intl.DateTimeFormat(undefined, { dateStyle: "medium" });
  return range.to
    ? `${format.format(range.from)} – ${format.format(range.to)}`
    : format.format(range.from);
}
