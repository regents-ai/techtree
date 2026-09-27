%{
  configs: [
    %{
      name: "default",
      files: %{
        included: ["mix.exs", "config/", "lib/"],
        excluded: [
          # Build artifacts are generated and are not application source.
          ~r"/_build/",
          # Dependency sources are third-party code.
          ~r"/deps/",
          # JavaScript dependencies are third-party code outside Credo's scope.
          ~r"/node_modules/",
          # Repository migrations are historical generated artifacts and excluded by custody.
          ~r"/priv/repo/migrations/",
          # Digested static assets are generated and excluded by custody.
          ~r"/priv/static/"
        ]
      },
      plugins: [],
      requires: [],
      strict: true,
      parse_timeout: 5000,
      color: true,
      checks: %{
        enabled: [
          {Credo.Check.Consistency.ExceptionNames, []},
          {Credo.Check.Consistency.LineEndings, []},
          {Credo.Check.Consistency.ParameterPatternMatching, []},
          {Credo.Check.Consistency.SpaceAroundOperators, []},
          {Credo.Check.Consistency.SpaceInParentheses, []},
          {Credo.Check.Consistency.TabsOrSpaces, []},
          {Credo.Check.Design.TagFIXME, []},
          {Credo.Check.Design.TagTODO, [exit_status: 2]},
          {Credo.Check.Readability.AliasOrder, []},
          {Credo.Check.Readability.FunctionNames, []},
          {Credo.Check.Readability.LargeNumbers, []},
          {Credo.Check.Readability.MaxLineLength, [priority: :low, max_length: 120]},
          {Credo.Check.Readability.ModuleAttributeNames, []},
          {Credo.Check.Readability.ModuleDoc, []},
          {Credo.Check.Readability.ModuleNames, []},
          {Credo.Check.Readability.ParenthesesInCondition, []},
          {Credo.Check.Readability.ParenthesesOnZeroArityDefs, []},
          {Credo.Check.Readability.PipeIntoAnonymousFunctions, []},
          {Credo.Check.Readability.PredicateFunctionNames, []},
          {Credo.Check.Readability.PreferImplicitTry, []},
          {Credo.Check.Readability.RedundantBlankLines, []},
          {Credo.Check.Readability.Semicolons, []},
          {Credo.Check.Readability.SpaceAfterCommas, []},
          {Credo.Check.Readability.StringSigils, []},
          {Credo.Check.Readability.TrailingBlankLine, []},
          {Credo.Check.Readability.TrailingWhiteSpace, []},
          {Credo.Check.Readability.UnnecessaryAliasExpansion, []},
          {Credo.Check.Readability.VariableNames, []},
          {Credo.Check.Readability.WithSingleClause, []},
          {Credo.Check.Refactor.Apply, []},
          {Credo.Check.Refactor.CondStatements, []},
          {Credo.Check.Refactor.CyclomaticComplexity, []},
          {Credo.Check.Refactor.FilterCount, []},
          {Credo.Check.Refactor.FilterFilter, []},
          {Credo.Check.Refactor.FunctionArity, []},
          {Credo.Check.Refactor.LongQuoteBlocks, []},
          {Credo.Check.Refactor.MapJoin, []},
          {Credo.Check.Refactor.MatchInCondition, []},
          {Credo.Check.Refactor.NegatedConditionsInUnless, []},
          {Credo.Check.Refactor.NegatedConditionsWithElse, []},
          {Credo.Check.Refactor.Nesting, []},
          {Credo.Check.Refactor.RedundantWithClauseResult, []},
          {Credo.Check.Refactor.RejectReject, []},
          {Credo.Check.Refactor.UnlessWithElse, []},
          {Credo.Check.Refactor.WithClauses, []},
          {Credo.Check.Warning.ApplicationConfigInModuleAttribute, []},
          {Credo.Check.Warning.BoolOperationOnSameValues, []},
          {Credo.Check.Warning.Dbg, []},
          {Credo.Check.Warning.ExpensiveEmptyEnumCheck, []},
          {Credo.Check.Warning.IExPry, []},
          {Credo.Check.Warning.IoInspect, []},
          {Credo.Check.Warning.MissedMetadataKeyInLoggerConfig, []},
          {Credo.Check.Warning.OperationOnSameValues, []},
          {Credo.Check.Warning.OperationWithConstantResult, []},
          {Credo.Check.Warning.RaiseInsideRescue, []},
          {Credo.Check.Warning.SpecWithStruct, []},
          {Credo.Check.Warning.StructFieldAmount, []},
          {Credo.Check.Warning.UnsafeExec, []},
          {Credo.Check.Warning.UnusedEnumOperation, []},
          {Credo.Check.Warning.UnusedFileOperation, []},
          {Credo.Check.Warning.UnusedKeywordOperation, []},
          {Credo.Check.Warning.UnusedListOperation, []},
          {Credo.Check.Warning.UnusedMapOperation, []},
          {Credo.Check.Warning.UnusedPathOperation, []},
          {Credo.Check.Warning.UnusedRegexOperation, []},
          {Credo.Check.Warning.UnusedStringOperation, []},
          {Credo.Check.Warning.UnusedTupleOperation, []},
          {Credo.Check.Warning.WrongTestFilename, []},
          # ExSlop catches patterns LLMs produce that experienced Elixir
          # developers do not. Registered as checks rather than as a plugin
          # because this config pins an explicit enabled list, which Credo
          # treats as authoritative over any plugin defaults.
          {ExSlop.Check.Warning.BlanketRescue, []},
          {ExSlop.Check.Warning.RescueWithoutReraise, []},
          {ExSlop.Check.Warning.RepoAllThenFilter, []},
          {ExSlop.Check.Warning.QueryInEnumMap, []},
          {ExSlop.Check.Warning.GenserverAsKvStore, []},
          {ExSlop.Check.Warning.PathExpandPriv,
           [
             files: %{
               excluded: [
                 # These read a priv file at compile time as an @external_resource,
                 # before the application has a build directory to ask for.
                 "lib/techtree/capabilities.ex",
                 "lib/techtree_web/live/changelog_live.ex"
               ]
             }
           ]},
          {ExSlop.Check.Warning.DualKeyAccess, []},
          {ExSlop.Check.Refactor.FilterNil, []},
          {ExSlop.Check.Refactor.RejectNil, []},
          {ExSlop.Check.Refactor.ReduceAsMap, []},
          {ExSlop.Check.Refactor.MapIntoLiteral, []},
          {ExSlop.Check.Refactor.IdentityPassthrough, []},
          {ExSlop.Check.Refactor.IdentityMap, []},
          {ExSlop.Check.Refactor.TryRescueWithSafeAlternative, []},
          {ExSlop.Check.Refactor.WithIdentityElse, []},
          {ExSlop.Check.Refactor.WithIdentityDo, []},
          {ExSlop.Check.Refactor.SortThenReverse, []},
          {ExSlop.Check.Refactor.StringConcatInReduce, []},
          {ExSlop.Check.Refactor.ReduceMapPut, []},
          {ExSlop.Check.Refactor.RedundantBooleanIf, []},
          {ExSlop.Check.Refactor.FlatMapFilter, []},
          {ExSlop.Check.Refactor.LengthComparison, []},
          {ExSlop.Check.Readability.NarratorDoc, []},
          {ExSlop.Check.Readability.BoilerplateDocParams, []},
          {ExSlop.Check.Readability.NarratorComment, []},
          {ExSlop.Check.Refactor.RedundantEnumJoinSeparator, []},
          {ExSlop.Check.Refactor.GraphemesLength, []},
          {ExSlop.Check.Refactor.ManualStringReverse, []},
          {ExSlop.Check.Refactor.SortThenAt, []},
          {ExSlop.Check.Refactor.SortForTopK, []},
          {ExSlop.Check.Refactor.ExplicitSumReduce, []},
          # credo_ash encodes the mechanically decidable rules of the
          # ash-regents playbook: policy coverage, actor placement, the
          # Ash-shaped N+1, and writes that go around Ash entirely.
          {CredoAsh.Check.Warning.PoliciesWithoutAuthorizer, []},
          {CredoAsh.Check.Warning.AuthorizerWithoutPolicies, []},
          {CredoAsh.Check.Warning.UnprotectedResource, []},
          {CredoAsh.Check.Warning.AshCallInLoop, []},
          {CredoAsh.Check.Warning.ActorOnExecution, []},
          {CredoAsh.Check.Warning.DirectRepoCall, []},
          {CredoAsh.Check.Warning.UnjustifiedAuthorizeFalse, []},
          {CredoAsh.Check.Design.WildcardAccept, []}
        ],
        disabled: [
          # AliasUsage is disabled because explicit qualification preserves domain and nested-adapter context.
          {Credo.Check.Design.AliasUsage, []},
          # UtcNowTruncate is a scheduled opt-in check, as in ash-template.
          {Credo.Check.Refactor.UtcNowTruncate, []},
          # MultiAliasImportRequireUse is controversial and intentionally left opt-in.
          {Credo.Check.Consistency.MultiAliasImportRequireUse, []},
          # UnusedVariableNames is controversial and intentionally left opt-in.
          {Credo.Check.Consistency.UnusedVariableNames, []},
          # DuplicatedCode is experimental and intentionally left opt-in.
          {Credo.Check.Design.DuplicatedCode, []},
          # SkipTestWithoutComment is controversial and intentionally left opt-in.
          {Credo.Check.Design.SkipTestWithoutComment, []},
          # AliasAs is controversial and intentionally left opt-in.
          {Credo.Check.Readability.AliasAs, []},
          # BlockPipe is controversial and intentionally left opt-in.
          {Credo.Check.Readability.BlockPipe, []},
          # ImplTrue is controversial and intentionally left opt-in.
          {Credo.Check.Readability.ImplTrue, []},
          # MultiAlias is controversial and intentionally left opt-in.
          {Credo.Check.Readability.MultiAlias, []},
          # NestedFunctionCalls is controversial and intentionally left opt-in.
          {Credo.Check.Readability.NestedFunctionCalls, []},
          # OneArityFunctionInPipe is controversial and intentionally left opt-in.
          {Credo.Check.Readability.OneArityFunctionInPipe, []},
          # OnePipePerLine is controversial and intentionally left opt-in.
          {Credo.Check.Readability.OnePipePerLine, []},
          # SeparateAliasRequire is controversial and intentionally left opt-in.
          {Credo.Check.Readability.SeparateAliasRequire, []},
          # SingleFunctionToBlockPipe is controversial and intentionally left opt-in.
          {Credo.Check.Readability.SingleFunctionToBlockPipe, []},
          # SinglePipe is controversial and intentionally left opt-in.
          {Credo.Check.Readability.SinglePipe, []},
          # Specs is opt-in because broad specification coverage is outside this lint adoption.
          {Credo.Check.Readability.Specs, []},
          # StrictModuleLayout is controversial and intentionally left opt-in.
          {Credo.Check.Readability.StrictModuleLayout, []},
          # WithCustomTaggedTuple is controversial and intentionally left opt-in.
          {Credo.Check.Readability.WithCustomTaggedTuple, []},
          # ABCSize is controversial and intentionally left opt-in.
          {Credo.Check.Refactor.ABCSize, []},
          # AppendSingleItem is controversial and intentionally left opt-in.
          {Credo.Check.Refactor.AppendSingleItem, []},
          # CondInsteadOfIfElse is controversial and intentionally left opt-in.
          {Credo.Check.Refactor.CondInsteadOfIfElse, []},
          # DoubleBooleanNegation is controversial and intentionally left opt-in.
          {Credo.Check.Refactor.DoubleBooleanNegation, []},
          # FilterReject is controversial and intentionally left opt-in.
          {Credo.Check.Refactor.FilterReject, []},
          # IoPuts is controversial and intentionally left opt-in.
          {Credo.Check.Refactor.IoPuts, []},
          # MapMap is controversial and intentionally left opt-in.
          {Credo.Check.Refactor.MapMap, []},
          # ModuleDependencies is experimental and intentionally left opt-in.
          {Credo.Check.Refactor.ModuleDependencies, []},
          # NegatedIsNil is controversial and intentionally left opt-in.
          {Credo.Check.Refactor.NegatedIsNil, []},
          # PassAsyncInTestCases is controversial and intentionally left opt-in.
          {Credo.Check.Refactor.PassAsyncInTestCases, []},
          # PipeChainStart is controversial and intentionally left opt-in.
          {Credo.Check.Refactor.PipeChainStart, []},
          # RejectFilter is controversial and intentionally left opt-in.
          {Credo.Check.Refactor.RejectFilter, []},
          # VariableRebinding is controversial and intentionally left opt-in.
          {Credo.Check.Refactor.VariableRebinding, []},
          # LazyLogging is controversial and intentionally left opt-in.
          {Credo.Check.Warning.LazyLogging, []},
          # LeakyEnvironment is controversial and intentionally left opt-in.
          {Credo.Check.Warning.LeakyEnvironment, []},
          # MapGetUnsafePass is controversial and intentionally left opt-in.
          {Credo.Check.Warning.MapGetUnsafePass, []},
          # MixEnv is controversial and intentionally left opt-in.
          {Credo.Check.Warning.MixEnv, []},
          # UnsafeToAtom is controversial and intentionally left opt-in.
          {Credo.Check.Warning.UnsafeToAtom, []}
        ]
      }
    }
  ]
}
