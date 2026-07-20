export class DomainError extends Error {
  constructor(
    readonly status: 400 | 404 | 409 | 422,
    message: string,
  ) {
    super(message);
    this.name = "DomainError";
  }
}

export class ValidationError extends DomainError {
  constructor(message: string) {
    super(400, message);
    this.name = "ValidationError";
  }
}

export class NotFoundError extends DomainError {
  constructor(message: string) {
    super(404, message);
    this.name = "NotFoundError";
  }
}

export class ConflictError extends DomainError {
  constructor(message: string) {
    super(409, message);
    this.name = "ConflictError";
  }
}

export class UnprocessableEntityError extends DomainError {
  constructor(message: string) {
    super(422, message);
    this.name = "UnprocessableEntityError";
  }
}
