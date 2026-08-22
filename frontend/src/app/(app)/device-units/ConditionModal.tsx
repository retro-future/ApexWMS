"use client";

import { Select } from "@mantine/core";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { FormModal } from "@/components/FormModal";
import { useDocumentAction } from "@/hooks/use-document";
import { errorMessage, notifySuccess } from "@/lib/notify";
import type { DeviceCondition, DeviceUnit } from "@/lib/types";

const CONDITIONS: DeviceCondition[] = ["new", "refurbished", "used"];

/** FR-2.18: condition is a pricing input, so changing it is a pricing act. */
export function ConditionModal({
  unit,
  onClose,
}: {
  unit: DeviceUnit;
  onClose: () => void;
}) {
  const t = useTranslations("deviceUnits");
  const tDoc = useTranslations("documents");
  const tCommon = useTranslations("common");

  const [condition, setCondition] = useState<DeviceCondition>(unit.condition);
  const [error, setError] = useState<string | null>(null);

  const change = useDocumentAction<DeviceUnit, { condition: DeviceCondition }>(
    "device-units",
    unit.id,
    { method: "PATCH", path: "/condition" },
  );

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    try {
      await change.mutateAsync({ condition });
      notifySuccess(t("conditionChanged"));
      onClose();
    } catch (thrown) {
      setError(errorMessage(thrown, tCommon("retry")));
    }
  }

  return (
    <FormModal
      opened
      onClose={onClose}
      title={t("changeConditionTitle")}
      onSubmit={submit}
      busy={change.isPending}
      error={error}
      submitLabel={tCommon("save")}
    >
      <Select
        label={t("condition")}
        description={t("changeConditionHint")}
        value={condition}
        onChange={(value) => setCondition((value ?? unit.condition) as DeviceCondition)}
        data={CONDITIONS.map((value) => ({
          value,
          label: tDoc(`condition.${value}`),
        }))}
        allowDeselect={false}
      />
    </FormModal>
  );
}
