import type { components } from "./api-types";

type S = components["schemas"];
export type Category = S["CategoryOut"];
export type CourseSummary = S["CourseSummary"];
export type CourseDetail = S["CourseDetail"];
export type CoursePage = S["CoursePage"];
export type Booking = S["BookingOut"];
export type BookingPage = S["BookingPage"];
export type Payment = S["PaymentOut"];
export type User = S["UserOut"];
export type AdminBooking = S["AdminBookingOut"];
export type NotificationPage = S["NotificationPage"];

export type BookingStatus =
  | "PENDING_PAYMENT" | "PAYMENT_PROCESSING" | "PAID" | "PENDING_APPROVAL"
  | "CONFIRMED" | "REJECTED" | "CANCELLED" | "EXPIRED" | "REFUNDED";
