import { Card, Center, Stack, Text, Title } from "@mantine/core";

/** The centred card every anonymous / account screen sits in. */
export function AuthShell({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <Center mih="100dvh" p="md">
      <Stack gap="lg" w="100%" maw={420}>
        <Stack gap="2xs" align="center">
          <Text fw={700} size="xl">
            ApexWMS
          </Text>
        </Stack>
        <Card withBorder shadow="sm" padding="xl" radius="md">
          <Stack gap="md">
            <Stack gap="2xs">
              <Title order={3}>{title}</Title>
              {subtitle && (
                <Text size="sm" c="dimmed">
                  {subtitle}
                </Text>
              )}
            </Stack>
            {children}
          </Stack>
        </Card>
      </Stack>
    </Center>
  );
}
