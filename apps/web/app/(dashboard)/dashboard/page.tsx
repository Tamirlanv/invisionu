import { redirect } from "next/navigation";

/** Кандидат сразу попадает в заявление; отдельной страницы «дашборд» нет. */
export default function DashboardPage() {
  redirect("/application/personal");
}
