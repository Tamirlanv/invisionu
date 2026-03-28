import { redirect } from "next/navigation";

export default function ApplicationIndex() {
  redirect("/application/personal");
}
