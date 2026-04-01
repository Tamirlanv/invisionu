import type { CommissionRole } from "./types";

export type CommissionPermissions = {
  canViewBoard: boolean;
  canOpenCandidate: boolean;
  canComment: boolean;
  canMove: boolean;
  canSetAttention: boolean;
  canExport: boolean;
  canSetStageStatus: boolean;
  canSetFinalDecision: boolean;
  canSetRubric: boolean;
  canSetInternalRecommendation: boolean;
};

export function permissionsFromRole(role: CommissionRole | null): CommissionPermissions {
  /** Backend may omit `commission_users` row for global admin; UI stays read-only unless role is explicit. */
  if (role === null) {
    return {
      canViewBoard: true,
      canOpenCandidate: true,
      canComment: false,
      canMove: false,
      canSetAttention: false,
      canExport: false,
      canSetStageStatus: false,
      canSetFinalDecision: false,
      canSetRubric: false,
      canSetInternalRecommendation: false,
    };
  }
  if (role === "admin") {
    return {
      canViewBoard: true,
      canOpenCandidate: true,
      canComment: true,
      canMove: true,
      canSetAttention: true,
      canExport: true,
      canSetStageStatus: true,
      canSetFinalDecision: true,
      canSetRubric: true,
      canSetInternalRecommendation: true,
    };
  }
  if (role === "reviewer") {
    return {
      canViewBoard: true,
      canOpenCandidate: true,
      canComment: true,
      canMove: true,
      canSetAttention: true,
      canExport: false,
      canSetStageStatus: true,
      canSetFinalDecision: true,
      canSetRubric: true,
      canSetInternalRecommendation: true,
    };
  }
  if (role === "viewer") {
    return {
      canViewBoard: true,
      canOpenCandidate: true,
      canComment: false,
      canMove: false,
      canSetAttention: false,
      canExport: false,
      canSetStageStatus: false,
      canSetFinalDecision: false,
      canSetRubric: false,
      canSetInternalRecommendation: false,
    };
  }
  return {
    canViewBoard: false,
    canOpenCandidate: false,
    canComment: false,
    canMove: false,
    canSetAttention: false,
    canExport: false,
    canSetStageStatus: false,
    canSetFinalDecision: false,
    canSetRubric: false,
    canSetInternalRecommendation: false,
  };
}

